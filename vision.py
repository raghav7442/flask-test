import base64
import requests
import os
import logging
import time
# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Function to process all images in the folder and send to LLM
def process_images(folder_name: str):
    # OpenAI API Key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error("OpenAI API key is not set.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # List all images in the folder
    image_files = [f for f in os.listdir(folder_name) if f.endswith('.jpg') or f.endswith('.jpeg') or f.endswith('.png')]

    # Iterate through each image
    for image_file in image_files:
        image_path = os.path.join(folder_name, image_file)
        
        # Encode the image in base64
        base64_image = encode_image(image_path)
        
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
            logging.info(f"LLM Response Content for {image_file}: {content}")
           
            
        else:
            # Log errors
            logging.error(f"Error: {response.status_code} for image {image_file}")
            logging.error(response.text)
