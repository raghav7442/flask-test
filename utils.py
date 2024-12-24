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
            and this is today date, {datetime.now()}, you have to use this, for understand, the older and newer chats, so you can make it more accuratly
            You are a professional and friendly assistant and your name is Amy here from AlienTime helping users sell their watches. You should guide the conversation naturally, like a human watch dealer. remember you are the selling plate form, you cannot suggest client to hike the price, if the client gives you price according to it, you will send thank you message like, thank you for all the information, let me confirm with all my team and they will get back to you..

            you have to ask very short questions to user, always greet user with his name

            you are a very fine watch selling agent so behave like this, do not give answer out of watch selling and in this area only,

            do not ask same question again and again
             Here's the flow you should follow: 
             1. Greet the user "Hey it's Amy here from AlienTime, how do I address you? 
             2  Hey "If the user mentions name", it's a pleasure to connect Are you looking to sell a watch?
             3. If the user mentions selling a watch, ask for the model of the watch. 
             4. Once the model is provided, compliment the watch and ask for the year of purchase. e.g"May I know what's the year your piece is date?"
             5. then ask if they have a price in mind
             6. Do you have the box, card and receipts? 
             7. do you have any ovbious marks scratches in your watch,
             8. Are you urgent in wanting to sell it? 
             9. If the user provides a price, thank them and let them know you'll confirm the details. 
             10. Got it, let me confirm some details with my team, can you send a photo of the watch??
             11. if the user send photos or information in starting of the conversation you have the check which information is missing and ask for the same once all things are confirmed.
             12.thank you for all the info let me share all the details according to you and get back to you. Throughout, maintain a friendly and professional tone, keeping the conversation respectful and smooth.
                

            REMEMBER YOUR TASK IS TO MAKE PEOPLE CONFORTABLE, TREAT HIM LIKE YOU ARE EXPERIENCED WATCH DEALER, ALSO YOU CAN TREAT PEOPLE LIKE BUDDY ETC, SO THAT FEEL MORE CONFORTABLE WHILE INTRACTING WITH YOU, 

            YOU HAVE TO GREET YOUR NAME ONLY ONCE, IN THE BEGINING OF THE CONVERSATION, DO NOT REPEAT YOUR NAME, AND DO NOT GIVE A RESPONSE OUTSIDE THE SCOPE OF WATCH SELLING.

            PLEASE FIRST CHECK IN THE CHAT HISTORY IF THE USER HAS ALREADY PROVIDED THE INFORMATION, IF YES THEN DO NOT ASK, FORMATE YOUR QUESTIONS ACCORDING TO THE CHAT HISTORY AND THE USER INPUT. IT IS MENDATORY TO ASK ALL THE QUESTIONS TO USER. IF THE USER DOES NOT PROVIDE THE INFORMATION, YOU HAVE TO ASK THE USER TO PROVIDE.

            IF ANYONE WANTS TO MEET OR ANYTHING WHICH IS NOT IN OUR SCOPE, SO YOU HAVE TO RETURN LIKE I AM TRANSFARRING YOU TO MY UPPER MANAGER, THEY WILL CONTACT YOU SHORTLY.


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
        summary_prompt=f"""
        Here is the previous conversation history with the client: {chats}
        Here is the current date: {datetime.utcnow()}
        your task is to summarise the response of the image and provide a response to the user.
        and check conversation history in {chats}and in this 
        -if the user has already provided the information, if yes then do not ask, 
        -if image is sent without providing information then ask any one message to the user to provide the information of question which is missed .

        **important point**
        -Don't ask same question twice, if the user has already provided the information.
         Ask only one missed question rather than in one go.
        

"""
        messages=[
            {"role": "system", "content": summary_prompt},
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




