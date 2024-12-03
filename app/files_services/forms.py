
from flask_wtf import FlaskForm
from wtforms import FileField
from flask_wtf.file import FileAllowed, FileRequired

class FileUploadForm(FlaskForm):
    file = FileField('file', validators=[FileRequired(), FileAllowed(['txt','jpg', 'png', 'jpeg', 'gif', 'pdf', 'xlx', 'doc', 'docx', 'xlsx'], 'All file support!')])
