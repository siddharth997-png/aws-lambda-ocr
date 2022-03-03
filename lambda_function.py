import json
from ocr import OCR
import urllib.parse
import boto3
import requests

print('Loading function')

s3 = boto3.client('s3')

def lambda_handler(event, context):
    #print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        print("file : " + key + " bucket : " + bucket)
        return response['ContentType']
    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e


# Executed when the Lambda function is called.
# Parameters:
#   base_64_string - string representing an image encoded using Base 64 format.
#   context        - contains AWS info.

# def lambda_handler(base_64_string: str, context):
#     ocr = OCR(debug_mode=False, aws_request_id=context.aws_request_id)
#     (status_code, recognized_text, confidence_values) = ocr.parse_image(base_64_string=base_64_string)

#     return {
#         'statusCode': json.dumps(status_code),
#         'recognizedText': json.dumps(recognized_text),
#         'confidenceValues': json.dumps(confidence_values)
#     }
