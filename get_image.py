import requests
import os
import logging


def get_image(wa_id, image_ids):
    """
    Fetch and save images from the list of image IDs.
    
    :param wa_id: WhatsApp ID used to name the folder.
    :param image_ids: List of image IDs to fetch.
    """
    
    # Ensure AUTH token is set
    auth_token = os.getenv("AUTH")
    if not auth_token:
        logging.error("Error: AUTH token not found")
        return
    
    # Create a folder named after the WhatsApp number (wa_id) if it doesn't exist
    folder_name = wa_id
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    headers = {
        'Authorization': auth_token  # Use the token
    }

    # Iterate through each image_id in the list
    for idx, image_id in enumerate(image_ids, start=1):
        url = f"https://crmapi.wa0.in/api/meta/v19.0/{image_id}?phone_number_id=418218771378739"

        # Send the request to fetch the image
        response = requests.get(url, headers=headers)

        # Check if the request was successful
        if response.status_code == 200:
            # Save each image with a unique name (output_image_1.jpg, output_image_2.jpg, etc.)
            image_path = os.path.join(folder_name, f'output_image_{idx}.jpg')
            with open(image_path, 'wb') as f:
                f.write(response.content)
            logging.info(f"Image {idx} saved as '{image_path}'")
        else:
            logging.error(f"Error: {response.status_code} for image ID: {image_id}")
            logging.error(response.text)
    
    
