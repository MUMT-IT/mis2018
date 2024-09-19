import os
import base64
import re
from flask import Flask, request, jsonify, render_template, redirect, url_for
import boto3
import psycopg2
from psycopg2 import sql
from werkzeug.utils import secure_filename
from botocore.exceptions import NoCredentialsError

from app.files_services import files_services

# Get the AWS credentials from Heroku environment variables set by Bucketeer

AWS_ACCESS_KEY_ID = os.getenv('BUCKETEER_AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('BUCKETEER_AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('BUCKETEER_AWS_REGION')
S3_BUCKET_NAME = os.getenv('BUCKETEER_BUCKET_NAME')

# Create an S3 client using credentials from Bucketeer

s3 = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

# Connect to PostgreSQL database on Heroku
def get_db_connection():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    return conn

# Function to check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_file_to_s3(file_path, file_name):
    try:
        s3.upload_file(file_path, S3_BUCKET_NAME, file_name)
        print(f"File {file_name} uploaded to S3 successfully.")
        return f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{file_name}"
    except NoCredentialsError:
        print("Credentials not available")
        return None

# Home route to display upload form
@files_services.route('/')
def index():
    return render_template('files_services/upload.html')
# Route for direct file upload by the user
@files_services.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part in request"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # content_type = file.content_type

        # Upload file to S3
        file_url = upload_file_to_s3(file, filename)

        if file_url:
            # Store the file URL in PostgreSQL
            conn = get_db_connection()
            cursor = conn.cursor()
            # Replace Table Here
            insert_query = sql.SQL("INSERT INTO files (file_name, file_url) VALUES (%s, %s)")
            cursor.execute(insert_query, (filename, file_url))
            conn.commit()

            cursor.close()
            conn.close()

            return redirect(url_for('/', success=True, file_url=file_url))
        else:
            return jsonify({"status": "error", "message": "Error uploading file"}), 500
    else:
        return jsonify({"status": "error", "message": "File type not allowed"}), 400
