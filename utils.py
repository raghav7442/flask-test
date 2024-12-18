import os
import logging
from openai import OpenAI
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta
from pymongo import MongoClient
load_dotenv()

class MongoDB:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI")
        self.client = MongoClient(mongo_uri)
        self.db = self.client["sellmywatch"]
        self.collection = self.db["chat_history"]

    def save_chat(self, wa_id, user_message, assistant_reply, message_type):
        chat_entry = {
            "user_message": user_message,
            "assistant_reply": assistant_reply,
            "type": message_type,
            "timestamp": datetime.utcnow(),
        }

        try:
            self.collection.update_one(
                {"wa_id": wa_id},
                {
                    "$set": {"wa_id": wa_id},
                    "$push": {"chats": chat_entry}
                },
                upsert=True
            )
          
        except Exception as e:
            logging.error(f"Error saving chat to MongoDB: {e}")

    def load_chat(self, wa_id):
        """
        Load the most recent chat history for a user.
        :param wa_id: WhatsApp ID of the user
        :param limit: Number of most recent messages to retrieve
        :return: A list of chat entries, or an empty list if no chat found
        """
        chat = self.collection.find_one({"wa_id": wa_id})
        if chat:
            # logging.info(chat)
            return chat["chats"][:]
          # Return the last `limit` messages
        return []


class WatchSellingAssistant:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=self.api_key)
        self.db = MongoDB()

    def get_assistant_response(self, wa_id, user_query):
        try:
            # Load past chat history for context
            chat_history = self.db.load_chat(wa_id)
            prompt= f"""
            here is the context or privisos chat of user, { chat_history}
            You are a professional and friendly assistant and your name is Amy here from AlienTime helping users sell their watches. You should guide the conversation naturally, like a human watch dealer. remember you are the selling plate form, you cannot suggest client to hike the price, if the client gives you price according to it, you will send thank you message like, thank you for all the information, let me confirm with all my team and they will get back to you..
            you have to ask very short questions to user, always greet user with his name

            you are a very fine watch selling agent so behave like this, do not give answer out of watch selling and in this area only,

            do not ask same question again and again
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
            messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_query}
        ]
            # Generate response
            response = self.openai_client.chat.completions.create(
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

    def summary_of_imgresponse(self, img_response, chats):
        prompt=f"""
        here is privious conversation to client{chats}
        here is current date{datetime.utcnow()}
        if you find the recent conversation where we are asking him about his name, watch model, purchase date, expected price, the watch image etc. you will not return any question to client, at all, else you cannot find any related message what i mentioned above, you will ask only one question to client after giving him all his details about the watch, you have to describe the watch first than you will ask one question to user if not there only
        Act and behave like a watch selling and answer generating agent, you will receive a single message which has multiple different messages, you have to give client a precise summary of his watch status given in the messages you receive, and ask a single question with the client, in the set of questions, you will receive some 4-5 question along with the messages, in those messages you have to form a best message, like

        first describe the watch condition with brand name if recived in the recived message,
        after that, if the qestions are availabe, ask one questions in those messages
     When you receive multiple responses from Vision regarding watches in the images, your task is to summarize them into one cohesive and detailed message. Follow these steps to structure the combined response:

        Steps to Create the Response
        Identify Similar Watches:
        If the watches in the images belong to the same brand or are the same model, consolidate the descriptions and highlight their common features.

        Distinguish Different Watches:
        If the watches belong to different brands or models, specify and differentiate them clearly in your message while ensuring the structure is easy to read.

        Ask for Missing Details:
        Include a request for additional details such as the year of purchase, price expectation, or original accessories. Rotate the questions to avoid repetition if multiple messages are involved.

        Ensure Clarity:
        Keep the message professional, well-structured, and grammatically accurate.
        for example if you receive messages like this,

                The image appears to show a watch from IWC Schaffhausen. It seems to be in excellent condition with no visible scratches.

                To proceed, could you please provide the following missing details?
                The image appears to show a watch from IWC Schaffhausen. It seems to be in excellent condition with no visible scratches

            

            you have to recreate the message like this

            here are two messages are ther, so we return the message like this,
            the both images are same, the watch watch from IWC Schaffhausen with a green dial and chronograph function. both appears to be in excellent condition with no visible scratches.
            to proceed further, you have to give us some detils, (in with in those 5 messages you have to ask one to user)
            i.e. can you share year of purchase of your watch?

"""
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": img_response}
        ]
            # Generate response
        response = self.openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=100,
            temperature=0.5,
        )
        assistant_reply = response.choices[0].message.content.strip()
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


