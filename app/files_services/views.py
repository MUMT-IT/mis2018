import os
import base64
import re
from flask import Flask, request, jsonify, render_template, redirect, url_for
import boto3
import psycopg2
from flask_login import login_required
from psycopg2 import sql
from werkzeug.utils import secure_filename
from botocore.exceptions import NoCredentialsError
from app.files_services import files_services

from io import BytesIO

from app.files_services.forms import FileUploadForm
from app.procurement.models import ProcurementDetail

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

# Function to check if the file extension is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def base64_to_local(base64_string, output_file_name_without_extension, output_folder='backup/files_image'):
    # Create the output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Extract the MIME type and Base64 data
    match = re.match(r"data:(.*?);base64,", base64_string)

    if match:
        mime_type = match.group(1)
        extension = mime_type.split('/')[-1]
        base64_data = base64_string.split(',')[1]
    else:
        base64_data = base64_string
        extension = "bin"  # Default extension if MIME type is unknown

    # Construct the full file path with the folder and file extension
    file_path = os.path.join(output_folder, f"{output_file_name_without_extension}.{extension}")

    # Decode the Base64 string to binary data
    file_data = base64.b64decode(base64_data)

    # Write the binary data to the file
    with open(file_path, 'wb') as file:
        file.write(file_data)

    print(f"File has been saved to {file_path}")
    return file_path

# Function to convert Base64 string to file
def base64_to_file(base64_string, output_file_name_without_extension):
    match = re.match(r"data:(.*?);base64,", base64_string)

    if match:
        mime_type = match.group(1)
        extension = mime_type.split('/')[-1]
        base64_data = base64_string.split(',')[1]
    else:
        base64_data = base64_string
        extension = "bin"

    file_path = f"{output_file_name_without_extension}.{extension}"
    file_data = base64.b64decode(base64_data)

    # with open(file_path, 'wb') as file:
    #     file.write(file_data)

    return file_path



def upload_file_to_s3(file_path, file_name):
    try:

        print(f"File {file_name} ready to S3.....")
        s3.upload_file(file_path, S3_BUCKET_NAME, file_name)
        # Upload the file and make it publicly accessible by setting ACL to 'public-read'
       # s3.upload_file(file_path, S3_BUCKET_NAME, file_name, ExtraArgs={'ACL': 'public-read'})

        print(f"File {file_name} uploaded to S3 successfully.")
        return f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{file_name}"
    except NoCredentialsError:
        print("Credentials not available")
        return None

@files_services.route('/procurement')
def procurement_view():
    return render_template('files_services/view_imgs.html')

@files_services.route('/files')
def get_procurement_image_data():
    #query = ProcurementDetail.query.all() #all record
    query = ProcurementDetail.query.filter(ProcurementDetail.image_url.isnot(None)).limit(3).all()

    # query = ProcurementDetail.query.filter_by(erp_code='0460058-401000065902-0') # Preview check data
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    total_filtered = query.count()
    query = query.offset(start).limit(length)

    data = []

    for item in query:
        item_data = item
        item_data['view_img'] = ('<img style="display:block; width:128px;height:128px;" id="image"'
            'src="{}">').format(item_data.get('image_url',''))
        data.append(item_data)

    return jsonify({'data': data,
                     'recordsFiltered': total_filtered,
                     'recordsTotal': ProcurementDetail.query.count(),
                     'draw': request.args.get('draw', type=int),
                     })


# Home route to display upload form
@files_services.route('/')
@login_required
def index():
    return render_template('files_services/upload.html')
#
# # Route for direct file upload by the user
@files_services.route('/upload_file', methods=['GET', 'POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part in request"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400

    if file and allowed_file(file.filename):
        # filename = secure_filename(file.filename)
        # content_type = file.content_type
        file_name = file.filename
        file_path = f"./{file_name}"

        # Save the file locally before uploading to S3
        file.save(file_path)


        # Upload file to S3
        file_url = upload_file_to_s3(file_path, file_name)




        if file_url:
            print('file', file_url)
            # # Store the file URL in PostgreSQL
            # conn = get_db_connection()
            # cursor = conn.cursor()
            # # Replace Table Here
            # insert_query = sql.SQL("INSERT INTO files (file_name, file_url) VALUES (%s, %s)")
            #
            # cursor.execute(insert_query, (filename, file_url))
            # conn.commit()
            # cursor.close()
            # conn.close()

            return redirect(url_for('/', success=True, file_url=file_url))
        else:
            return jsonify({"status": "error", "message": "Error uploading file"}), 500
    else:
        return jsonify({"status": "error", "message": "File type not allowed"}), 400


@files_services.route('/post')
def post_all_files_to_s3():
    query = ProcurementDetail.query
    data = []
    for item in query:
        item_data = item.to_dict()
        data_file = ''
        base64code = 'data:image/png;base64, {}'.format(item_data['image'])
        if item_data['image'] != '':
            data_file = base64_to_local(base64code, item_data['erp_code'])
        item_data['view_img'] = ('<img style="display:block; width:128px;height:128px;" id="base64image"'
                                 'src="data:image/png;base64, {}">').format(item_data['image'])

        item_data["Base64Code"] = data_file
        data.append(item_data)
        return jsonify({'data': data})

    @files_services.route('/view_post')
    @login_required
    def submit_view():
        return render_template('files_services/view_submit.html')