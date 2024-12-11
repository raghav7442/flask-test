import base64
import requests
import os
import logging
import time
from utils import *


def image_to_base64(url):
    response = requests.get(url)
    if response.status_code == 200:
        return base64.b64encode(response.content).decode('utf-8')
    else:
        raise Exception("Failed to fetch image")

# Function to process all images in the folder and send to LLM
def process_images(image_url: str, chat_history: any):
    # OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error("OpenAI API key is not set.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Encode the image in base64
    base64_image = image_to_base64(image_url)

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""
                        Here is the previous chat history of the user: {chat_history}.

                        You are a highly skilled watch-selling agent, so respond accordingly. Please focus only on watch-related discussions. Follow these rules:

                        **Image Analysis Rules:**
                        - If an image is provided:
                          1. Determine if the image shows a watch.
                          2. Describe the watch, including its brand, condition, and any scratches or damage (with the count and severity if applicable).
                          3. If the watch appears in excellent condition with no scratches, respond: "The watch appears to be in excellent condition with no visible scratches. Thanks for sharing. Our team will contact you shortly."
                          4. If scratches or damage are visible, respond with details, e.g., "The watch has [X] visible scratches [or damage]. Thanks for sharing. Our team will contact you shortly."
                          5. If the image is blurry, request a clearer image: "The image seems blurry. Could you please upload a clearer picture of the watch?"
                          6. If the image is not related to a watch, respond: "It seems the image is not related to a watch. Kindly share an image of the watch you wish to sell."

                        **Text Analysis Rules:**
                        - From the chat history, check if the user has provided:
                          1. Name
                          2. Watch model
                          3. Purchase year
                          4. Urgency to sell
                          5. Price expectation
                          6. Original box, bill, and warranty card details
                        - If any detail is missing, politely ask only for the missing information, e.g., "Thank you for the details provided so far. May I have your name, please?" or "It seems you haven’t mentioned if you have the original bill and box of the watch. Could you confirm?"

                        **Final Response Rules:**
                        - Once all necessary information is gathered, conclude with: "Thank you for providing all the details. Our team will contact you shortly to proceed further."

                        **Avoid Repetition Rules:**
                        - Do not ask repetitive questions if the information is already available in the chat history.
                        - Ensure the chatbot’s responses are concise, relevant, and strictly focused on watch selling.
                        - Stop asking questions once all required details are gathered.
                        """
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300
    }

    # Send the request to OpenAI API
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

    if response.status_code == 200:
        response_json = response.json()
        # Extract the 'content' from the response
        content = response_json['choices'][0]['message']['content']
        # Log the content only
        logging.info(f"LLM Response Content for: {content}")

        return content

    else:
        # Log errors
        logging.error(f"Error: {response.status_code} for image")
        logging.error(response.text)
