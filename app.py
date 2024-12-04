import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
import json
import time
import random

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
            if assistant_reply not in open(file_path).read():  # Avoid duplicate saving
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
                {"role": "system", "content": """You are Amy from AlienTime, a professional and friendly assistant helping users sell their watches. Follow these steps for smooth interactions:
                1. Greet the user and ask their name. 
                2. Ask if they're looking to sell a watch.
                3. Ask for the model, year of purchase, and price range.
                4. Ask for details like original box, warranty card, and scratches.
                5. Request a photo of the watch.
                6. Send one clear reply, avoid duplicates, and confirm receipt of details.
                7. Thank the user and inform them your team will contact them shortly. 
                Always maintain a friendly, professional tone and avoid suggesting price changes."""
                },
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

app = Flask(__name__)
app.secret_key = "supersecretkey"
assistant = WatchSellingAssistant()
whatsapp_api = WhatsAppAPI(assistant)

@app.route('/', methods=['GET'])
def check():
    return "API IS RUNNING FINE", 200

@app.route('/userChat', methods=['GET', 'POST'])
def user_chat():
    logging.info("Received a request.")
    if request.method == 'GET':
        challenge = request.args.get('challenge')
        if challenge:
            return challenge, 200
        return "No challenge", 400

    elif request.method == 'POST':
        if request.is_json:
            data = request.json
            try:
                wa_id = str(data['data']['message']['phone_number'])
                message_type = data['data']['message']['message_type']

                logging.info(f"Mobile number: {wa_id}")

                if message_type == 'TEXT':
                    body_content = data['data']['message']['message_content']['text']
                    time.sleep(random.randint(35, 45))  # Add delay
                    assistant_response = assistant.get_assistant_response(wa_id, body_content)
                    whatsapp_api.send_message(wa_id, assistant_response)
                    return jsonify({"message": "Text processed"}), 200

                elif message_type == 'IMAGE':
                    image_ids_list = data['data']['message']['message_content']['url']
                    time.sleep(random.randint(35, 45))  # Add delay
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
    app.run(debug=True, host='0.0.0.0', port=5000)
