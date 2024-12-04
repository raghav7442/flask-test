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
        return "Error: Missing API Key."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        # Encode the image in base64
        base64_image = image_to_base64(image_url)

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": f"You are an assistant helping analyze watch images. Describe the watch, including its brand, condition, scratches, and overall details. Here's the image: data:image/jpeg;base64,{base64_image}"
                }
            ],
            "max_tokens": 300
        }

        # Send the request to OpenAI API
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        if response.status_code == 200:
            response_json = response.json()
            # Extract the 'content' from the response
            content = response_json['choices'][0]['message']['content'].strip()
            if not content or "unable to" in content.lower():
                # If the response is not meaningful, fallback to error message
                return "Sorry, I couldn't analyze the image. Please upload a clearer image or provide more details."
            return content  # Return the watch details as a string
        else:
            logging.error(f"Error: {response.status_code} for image")
            logging.error(response.text)
            return "Sorry, I couldn't analyze the image. Please upload a clearer image or provide more details."

    except Exception as e:
        logging.error(f"Exception occurred while processing image: {e}")
        return "Sorry, I couldn't process the image. Please try again."
