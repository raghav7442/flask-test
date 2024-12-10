import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import requests
import json
from vision import process_images
from datetime import datetime, timedelta
import threading
from pymongo import MongoClient
from utils import *
load_dotenv()

user_message_buffer = {}  # Structure: {wa_id: {"messages": [], "timer": Timer}}

def process_messages(wa_id):
    """Process and send accumulated messages after the delay."""
    global user_message_buffer
    mongodb=MongoDB()
    if wa_id in user_message_buffer:
        # Combine all messages in the buffer
        messages = user_message_buffer[wa_id]["messages"]
        combined_message = " ".join(messages).strip()

        # Clear the buffer for this user
        del user_message_buffer[wa_id]

        if combined_message:
            # Generate AI assistant response
            assistant_response = assistant.get_assistant_response(wa_id, combined_message)
            mongodb.save_chat(wa_id,combined_message,assistant_response,"TEXT")
            # Send the response via WhatsApp
            whatsapp_api.send_message(wa_id, assistant_response)
            logging.info(assistant_response)


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
                mongodb=MongoDB()
        
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
                    # logging.info(f"assistant_image\n {image_ids_list}")
                    chat=mongodb.load_chat(wa_id)
                    imgResponse = process_images(image_ids_list,chat)

                    logging.info(f"image response{imgResponse}")
                    whatsapp_api.send_message(wa_id, imgResponse)
                    mongodb.save_chat(wa_id,image_ids_list,imgResponse,"IMAGE")
                    
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
