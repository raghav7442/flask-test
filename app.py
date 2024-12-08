import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
import json
from get_image import get_image
from vision import process_images
from datetime import datetime, timedelta
import threading
from pymongo import MongoClient
load_dotenv()
class MongoDB:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.client = MongoClient(mongo_uri)
        self.db = self.client["chat_database"]
        self.collection = self.db["chat_history"]

    def save_chat(self, wa_id, user_message, assistant_reply, message_type):
        chat_entry = {
            "user_message": user_message,
            "assistant_reply": assistant_reply,
            "type": message_type,
            "timestamp": datetime.utcnow(),
        }

        existing_chat = self.collection.find_one({"wa_id": wa_id})
        if existing_chat:
            self.collection.update_one(
                {"wa_id": wa_id},
                {"$push": {"chat_history": chat_entry}}
            )
        else:
            new_chat = {
                "wa_id": wa_id,
                "chat_history": [chat_entry],
                "created_at": datetime.utcnow()
            }
            self.collection.insert_one(new_chat)

    def load_chat(self, wa_id, limit=10):
        """
        Load the most recent chat history for a user.
        :param wa_id: WhatsApp ID of the user
        :param limit: Number of most recent messages to retrieve
        :return: A list of chat entries, or an empty list if no chat found
        """
        chat = self.collection.find_one({"wa_id": wa_id})
        if chat:
            return chat["chat_history"][-limit:]  # Return the last `limit` messages
        return []


class WatchSellingAssistant:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.db = MongoDB()

    def get_assistant_response(self, wa_id, prompt):
        try:
            # Load past chat history for context
            chat_history = self.db.load_chat(wa_id, limit=10)
            prompt= """You are a professional and friendly assistant and your name is Amy here from AlienTime helping users sell their watches. You should guide the conversation naturally, like a human watch dealer. remember you are the selling plate form, you cannot suggest client to hike the price, if the client gives you price according to it, you will send thank you message like, thank you for all the information, let me confirm with all my team and they will get back to you..
             Here's the flow you should follow: 
             1. Greet the user "Hey it's Amy here from AlienTime, how do I address you? 
             2  Hey "If the user mentions name", it's a pleasure to connect Are you looking to sell a watch?
             3. If the user mentions selling a watch, ask for the model of the watch. 
             4. Once the model is provided, compliment the watch and ask for the year of purchase. 
             5. then ask if they have a price in mind
             6. Do you have original box and bill and warranty card with you? 
             7. do you have any ovbious marks scratches in your watch,
             8. Are you urgent in wanting to sell it? 
             9. If the user provides a price, thank them and let them know you'll confirm the details. 
             10. Got it, let me confirm some details with my team, can you send a photo of the watch??
             11. if the user send photos or information in starting of the conversation you have the check which information is missing and ask for the same once all things are confirmed.
             12.thank you for all the info let me share all the details according to you and get back to you. Throughout, maintain a friendly and professional tone, keeping the conversation respectful and smooth.
             """
            messages = [{"role": "system", "content": """You are a professional and friendly assistant named Amy...""" }]

            # Add chat history to context
            for entry in chat_history:
                messages.append({"role": "user", "content": entry["user_message"]})
                messages.append({"role": "assistant", "content": entry["assistant_reply"]})

            # Add the current prompt
            messages.append({"role": "user", "content": prompt})

            # Generate response
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            )
            assistant_reply = response.choices[0].message.content.strip()
            return assistant_reply
        except Exception as e:
            logging.error(f"OpenAI API request failed: {e}")
            return "I'm sorry, but I couldn't process your request at the moment."

    def reply_and_save(self, wa_id, user_message, message_type):
        """
        Generate reply and save chat history to MongoDB.
        :param wa_id: WhatsApp ID of the user
        :param user_message: User's message
        :param message_type: Message type ('TEXT' or 'IMAGE')
        :return: Assistant's reply
        """
        if message_type == 'TEXT':
            assistant_reply = self.get_assistant_response(wa_id, user_message)
        elif message_type == 'IMAGE':
            assistant_reply = "It seems you have sent an image. Our team will review it shortly."
        else:
            assistant_reply = "Unhandled message type."

        # Save conversation to MongoDB
        self.db.save_chat(wa_id, user_message, assistant_reply, message_type)

        return assistant_reply



class AiSensyAPI:
    def __init__(self):
        self.api_url = f"https://apis.aisensy.com/project-apis/v1/project/{os.getenv('AISENSY_PROJECT_ID')}/messages"
        
        self.auth_header = {
            'X-AiSensy-Project-API-Pwd': os.getenv('AISENSY_APP_PWD'),
            'Content-Type': 'application/json',
            'Accept': "application/json",
        }

    def send_message(self, to, message):
        payload = json.dumps({
            "to": to,
            "type": "text",
            "recipient_type": "individual",
            "text": {
                "body": message
            }
        })

        try:
            response = requests.post(self.api_url, headers=self.auth_header, data=payload)
            if response.status_code == 200:
                logging.info("Message sent successfully")
                return True
            else:
                logging.error(f"Failed to send message: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logging.error(f"Exception occurred while sending message: {e}")
            return False

class WhatsAppAPI:
    def __init__(self, assistant):
        self.assistant = assistant
        self.aisensy_api = AiSensyAPI()

    def send_message(self, to, message):
        success = self.aisensy_api.send_message(to, message)
        if success:
            logging.info(f"Message to {to}: {message}")
        else:
            logging.error(f"Failed to send message to {to}")

# Temporary buffer for batching user messages
# Global buffer for batching user messages
user_message_buffer = {}  # Structure: {wa_id: {"messages": [], "timer": Timer}}

def process_messages(wa_id):
    """Process and send accumulated messages after the delay."""
    global user_message_buffer

    if wa_id in user_message_buffer:
        # Combine all messages in the buffer
        messages = user_message_buffer[wa_id]["messages"]
        combined_message = " ".join(messages).strip()

        # Clear the buffer for this user
        del user_message_buffer[wa_id]

        if combined_message:
            # Generate AI assistant response
            assistant_response = assistant.get_assistant_response(wa_id, combined_message)

            # Send the response via WhatsApp
            whatsapp_api.send_message(wa_id, assistant_response)

def add_message_to_buffer(wa_id, body_content):
    """Add a message to the buffer and schedule processing."""
    global user_message_buffer

    if wa_id not in user_message_buffer:
        # Initialize a new buffer entry for this user
        user_message_buffer[wa_id] = {"messages": [], "timer": None}

    # Append the new message to the user's message queue
    user_message_buffer[wa_id]["messages"].append(body_content)

    # Reset the timer (if one exists) or start a new one
    if user_message_buffer[wa_id]["timer"]:
        user_message_buffer[wa_id]["timer"].cancel()  # Cancel the existing timer

    # Start a new timer for delayed processing
    user_message_buffer[wa_id]["timer"] = threading.Timer(30, process_messages, args=(wa_id,))
    user_message_buffer[wa_id]["timer"].start()


# Flask App Setup
app = Flask(__name__)
app.secret_key = "supersecretkey"
assistant = WatchSellingAssistant()
whatsapp_api = WhatsAppAPI(assistant)

@app.route('/', methods=['GET'])
def check():
    return "API IS RUNNING FINE", 200

@app.route('/userChat', methods=['GET', 'POST'])
def user_chat():
    if request.method == 'GET':
        challenge = request.args.get('challenge')
        print( challenge)
        if challenge:
            return challenge, 200
        return "No challenge", 400

    elif request.method == 'POST':
        if request.is_json:
            data = request.json
            try:
                # Extract WhatsApp ID and message details
                wa_id = str(data['data']['message']['phone_number'])
        
                #message_info = data['data']['message']['message_content']['text']
                message_type = data['data']['message']['message_type']

                # image=data['data']['message']['message_content']['url']
                logging.info(f"mobile number- {wa_id}")

                if message_type == 'TEXT':
                    body_content = data['data']['message']['message_content']['text']
                    add_message_to_buffer(wa_id, body_content)
                
                    return jsonify({"message": "Text processed"}), 200
                

                elif message_type == 'IMAGE':
                    image_ids_list = data['data']['message']['message_content']['url']
                    assistant_response = assistant.get_assistant_response(wa_id, image_ids_list)
                    logging.info(f"assistant_image\n {image_ids_list}") 
                    logging.info(f"assistant_reply\n {assistant_response}") 

                    imgResponse = process_images(image_ids_list)
                    # response_message = "Thanks for sharing the image; our team will contact you shortly."
                    whatsapp_api.send_message(wa_id, assistant_response)
                    whatsapp_api.send_message(wa_id, imgResponse)
                    return jsonify({"message": "Image processed"}), 200

                else:
                    return jsonify({"error": "Unhandled message type"}), 400

            except (KeyError, IndexError) as e:
                logging.error(f"Error extracting data: {e}")
                return jsonify({"error": "Invalid data format"}), 400

            except Exception as e:
                logging.error(f"Error processing message: {e}")
                return jsonify({"error": "Failed to process message"}), 500

        else:
            return jsonify({"error": "Unsupported Media Type"}), 415

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, host='0.0.0.0', port=5000)
