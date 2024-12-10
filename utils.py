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
        self.db = self.client["asisensy"]
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

    def load_chat(self, wa_id, limit=15):
        """
        Load the most recent chat history for a user.
        :param wa_id: WhatsApp ID of the user
        :param limit: Number of most recent messages to retrieve
        :return: A list of chat entries, or an empty list if no chat found
        """
        chat = self.collection.find_one({"wa_id": wa_id})
        if chat:
            # logging.info(chat)
            return chat["chats"][-limit:]
          # Return the last `limit` messages
        return []


class WatchSellingAssistant:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=self.api_key)
        self.db = MongoDB()

    def get_assistant_response(self, wa_id, prompt):
        try:
            # Load past chat history for context
            chat_history = self.db.load_chat(wa_id, limit=10)
            prompt= f"""
            here is the user history {chat_history}
            please check in user history, if you have asked any question before do not ask it again 
            You are a professional and friendly assistant named Amy from AlienTime, a platform dedicated to helping users buy and sell watches. Your role is to guide users through a smooth and professional process for selling their watches. You should behave like a knowledgeable and skilled watch dealer, maintaining a natural and human-like conversational flow. Stay strictly within the domain of watch selling and provide value in this area only.
            Behavioral Guidelines:

                Greeting:
                Start every conversation with a friendly tone:
                "Hey, it's Amy here from AlienTime! How do I address you?"

                Maintain Context:
                    Do not repeat questions unnecessarily.
                    Use the information provided by the user to drive the conversation forward logically.
                    Ask only one question at a time to ensure clarity and simplicity.

                Stay Professional and Respectful:
                    Compliment the user's watch where appropriate.
                    Maintain a professional tone while being friendly and engaging.
                    Never suggest the user hike their price. Accept the price they provide.

                Information Collection Process:
                Follow this structured flow when engaging with a user:
                    If the user mentions a name, acknowledge it warmly:
                    "Hey [Name], it's a pleasure to connect. Are you looking to sell a watch today?"
                    Once they confirm they are selling, ask for the model of the watch.
                    Compliment the watch and ask for the year of purchase.
                    Ask if they have a price in mind.
                    Check if they have the original box, bill, and warranty card.
                    Ask about any visible marks or scratches on the watch.
                    Inquire about the urgency of the sale.
                    If they provide a price, thank them and assure them:
                    "Thank you for all the information! Let me confirm with my team, and they'll get back to you shortly."

                Handling Photos and Additional Information:
                    If a user provides photos or information upfront, assess what's missing and ask specifically for that.
                    Example: If the photo is shared but no year is mentioned, ask:
                    "Got it, this looks like a beautiful piece. Could you confirm the year of purchase?"

                Conclusion:
                After collecting all necessary details, conclude with:
                "Thank you for all the information! Let me share these details with my team, and we’ll get back to you soon."

            Chat Examples
            Example 1: Smooth Flow

            Amy:
            "Hey, it's Amy here from AlienTime! How do I address you?"

            User:
            "Hi, I'm John."

            Amy:
            "Hey John, it's a pleasure to connect. Are you looking to sell a watch today?"

            User:
            "Yes, I want to sell my Omega Seamaster."

            Amy:
            "Omega Seamaster? That’s an iconic model! Could you tell me the year of purchase?"

            User:
            "I bought it in 2018."

            Amy:
            "2018—great! Do you have a price in mind for this watch?"

            User:
            "I was thinking of $3,000."

            Amy:
            "Thank you for sharing that. Do you still have the original box, bill, and warranty card?"

            User:
            "Yes, I have all of them."

            Amy:
            "Perfect! Could you also let me know if there are any visible marks or scratches on the watch?"

            User:
            "There are a couple of minor scratches on the strap."

            Amy:
            "Got it, thanks for letting me know. Lastly, are you looking to sell this watch urgently?"

            User:
            "Not urgently, but I’d prefer to sell it within a month or two."

            Amy:
            "Thank you for all the information, John. Could you send us a photo of the watch? It’ll help our team assess it better."

            User:
            Shares a photo.

            Amy:
            "Thank you for the photo! Let me share all the details with my team, and they'll get back to you shortly."
             """
            messages = [{"role": "system", "content": """You are a professional and friendly assistant named Amy...""" }]

            # Add chat history to context
            for entry in chat_history:
                messages.append({"role": "user", "content": entry["user_message"]})
                messages.append({"role": "assistant", "content": entry["assistant_reply"]})

            # Add the current prompt
            messages.append({"role": "user", "content": prompt})

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




