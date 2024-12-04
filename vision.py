import base64
import requests
import os
import logging
import time

# Function to encode the image
def image_to_base64(url):
    response = requests.get(url)
    if response.status_code == 200:
        return base64.b64encode(response.content).decode('utf-8')
    else:
        raise Exception("Failed to fetch image")

# Function to process all images in the folder and send to LLM
def process_images(image_url: str):
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
                        "text": "you are a helpful assistant, you will get the images of watch, you will describe the image, also it's brand, you will find the scratches on the watch and its condition, you will return the message of the condition of the watch, that if it looks like new watch and there are no scratches and everything is fine, you will return the message that it looks fine, if the watch have scratches you will find the count of the scratches and it's quality, if the image is blur you will send user a message that, he need to upload the same image in a good quality"
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
        
        
    else:
        # Log errors
        logging.error(f"Error: {response.status_code} for image")
        logging.error(response.text)
