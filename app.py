import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
import json
from get_image import get_image  # Ensure you have this module
from vision import process_images  # Ensure you have this module

load_dotenv()

class WatchSellingAssistant:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.memory_dir = "user_memory"
        self.initialize_memory_dir()

    def initialize_memory_dir(self):
        if not os.path.exists(self.memory_dir):
            os.makedirs(self.memory_dir)

    def get_user_memory_file(self, wa_id):
        return os.path.join(self.memory_dir, f"{wa_id}_memory.txt")

    def save_to_memory(self, wa_id, user_message, assistant_reply):
        file_path = self.get_user_memory_file(wa_id)
        with open(file_path, "a") as f:
            f.write(f"User: {user_message}\n")
            f.write(f"Assistant: {assistant_reply}\n")

    def load_from_memory(self, wa_id):
        file_path = self.get_user_memory_file(wa_id)
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return f.read()
        return ""

    def get_assistant_response(self, wa_id, prompt):
        try:
            history = self.load_from_memory(wa_id)
            messages = [
                {"role": "system", "content": """You are a professional and friendly assistant helping users sell their watches. You should guide the conversation naturally, like a human watch dealer. remember you are the selling plate form, you cannot suggest client to hike the price, if the client gives you price according to it, you will send thank you message like, thank you for all the information, let me confirm with all my team and they will get back to you..
             Here's the flow you should follow: 
             1. Greet the user warmly and ask how you can assist them. 
             2. If the user mentions selling a watch, ask for the model of the watch. 
             3. Once the model is provided, compliment the watch and ask for the year of purchase. 
            4. then ask if they have a price in mind
             5. Do you have original box and bill and warranty card with you? 
             6. do you have any ovbious marks scratches in your watch,
             7. Are you urgent in wanting to sell it? 
             8. If the user provides a price, thank them and let them know you'll confirm the details. 
             9. Got it, let me confirm some details with my team, can you send a photo of the watch??
            10.thank you for all the info let me share all the details according to you and get back to you. Throughout, maintain a friendly and professional tone, keeping the conversation respectful and smooth."""},
                
            ]
            
            if history:
                for line in history.splitlines():
                    if line.startswith("User:"):
                        messages.append({"role": "user", "content": line[6:]})
                    elif line.startswith("Assistant:"):
                        messages.append({"role": "assistant", "content": line[11:]})

            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=150,
                n=1,
                stop=None,
                temperature=0.7,
            )
            assistant_reply = response.choices[0].message.content.strip()
            self.save_to_memory(wa_id, prompt, assistant_reply)
            return assistant_reply
        except Exception as e:
            logging.error(f"OpenAI API request failed: {e}")
            return "I'm sorry, but I couldn't process your request at the moment."

class AiSensyAPI:
    def __init__(self):
        self.api_url = "https://api.aisensy.com/send-message"
        self.auth_header = {
            'Authorization': os.getenv('AISENSY_API_KEY'),
            'Content-Type': 'application/json',
            'Accept': "application/json",
        }

    def send_message(self, to, message):
        payload = json.dumps({
            "recipient_type": "individual",
            "to": to,
            "type": "text",
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

app = Flask(__name__)
app.secret_key = "supersecretkey"
assistant = WatchSellingAssistant()
whatsapp_api = WhatsAppAPI(assistant)

@app.route('/', methods=['GET'])
def check():
    return "API IS RUNNING FINE", 200

@app.route('/userChat', methods=['GET', 'POST'])
def user_chat():
    print(request)
    if request.method == 'GET':
        challenge = request.args.get('challenge')
        print( challenge)
        if challenge:
            return challenge, 200
        return "No challenge", 400

    elif request.method == 'POST':
        if request.is_json:
            data = request.json
            print(data)
            try:
                # Extract WhatsApp ID and message details
                wa_id = data['entry'][0]['changes'][0]['value']['contacts'][0]['wa_id']
                message_info = data['entry'][0]['changes'][0]['value']['messages'][0]

                if message_info['type'] == 'text':
                    body_content = message_info['text']['body']
                    assistant_response = assistant.get_assistant_response(wa_id, body_content)
                    whatsapp_api.send_message(wa_id, assistant_response)
                    return jsonify({"message": "Text processed"}), 200

                elif message_info['type'] == 'image':
                    image_ids_list = [message['image']['id'] for message in data['entry'][0]['changes'][0]['value']['messages']]
                    get_image(wa_id, image_ids_list)
                    process_images(wa_id)
                    response_message = "Thanks for sharing the image; our team will contact you shortly."
                    whatsapp_api.send_message(wa_id, response_message)
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
    app.run(debug=True,host='0.0.0.0', port=5000)