import json
from ocr import OCR
import uuid
from urllib.parse import unquote_plus
from urllib.request import urlopen
import urllib.parse
import boto3
import base64

print('Loading function')

s3 = boto3.client('s3')

def createUrl(event):
    header = 'https://'
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    aws_region = event['Records'][0]['awsRegion']

    url = header + '.' + bucket_name + 's3' + '.' + aws_region + '.' + 'amazonaws.com/' + key
    return url

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event 
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    #Get the object bucket and key, and print them
    print("file : " + key + " bucket : " + bucket)

    #Generate the presigned url for the object
    
    url = s3.generate_presigned_url('get_object',
                                Params={
                                    'Bucket': bucket,
                                    'Key': key,
                                },                                  
                                ExpiresIn=3600)
    

    #url = 'https://test-bucket997.s3.ap-south-1.amazonaws.com/op1.jpg'
    #url = createUrl(event)
    print('url : ' + url)

    try:
        #converting image to base 64 since ocr function expects base 64 encoded image 
        '''
        with open(url, "rb") as img_file:
            base_64_string = base64.b64encode(img_file.read())
        '''

        base_64_string = base64.b64encode(urlopen(url).read())

        #print("Encoded string : " + base_64_string)
    
        print("encoding successful")

        #calling ocr on encoded string
        ocr = OCR(debug_mode=False, aws_request_id=context.aws_request_id)
        (status_code, recognized_text, confidence_values) = ocr.parse_image(base_64_string=base_64_string)

        print("status code : ")
        print(status_code)
        print("text : ")
        print(recognized_text)

        return {
            'statusCode': json.dumps(status_code),
            'recognizedText': json.dumps(recognized_text),
            'confidenceValues': json.dumps(confidence_values)
        }
    except Exception as e:
        print(e)
        raise e


# url = s3.generate_presigned_url('get_object',
#                                 Params={
#                                     'Bucket': 'mybucket',
#                                     'Key': 'upload/nocturnes.png',
#                                 },                                  
#                                 ExpiresIn=3600)

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
