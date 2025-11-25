from flask import Flask, request, render_template_string
import boto3
import pymysql
import json
import PyPDF2

app = Flask(__name__)

AWS_REGION = "us-east-1"
S3_BUCKET = "your-bucket-name"
RDS_HOST = "your-rds-name-cfwuo4egyshz.us-east-1.rds.amazonaws.com"
RDS_DB = "your-rds-name"
RDS_USER = "flask_user"
RDS_PASSWORD = "your-strong-password"

s3 = boto3.client('s3', region_name=AWS_REGION)
bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>PDF Summarization - Bedrock</title>
</head>
<body style="font-family: Arial; text-align:center; margin-top: 50px;">
   <h2>📄 Upload PDF for Summarization</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
 <input type="file" name="pdf_file" required>
        <button type="submit">Upload</button>
    </form>
    {% if summary %}
    <h3>🧠 Summary:</h3>
    <p style="text-align:left; white-space: pre-wrap;">{{ summary }}</p>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_PAGE)

@app.route('/upload', methods=['POST'])
def upload():
    try:
        file = request.files['pdf_file']
        filename = file.filename
        filepath = f"/tmp/{filename}"
        file.save(filepath)

        s3.upload_file(filepath, S3_BUCKET, filename)

        pdf_text = ""
        with open(filepath, "rb") as f:
 reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                page_text = " ".join(page_text.split())
                pdf_text += page_text + "\n"

        if not pdf_text.strip():
            return "⚠️ No readable text found in the PDF.", 400

        prompt = f"Summarize the following text clearly and briefly:\n\n{pdf_text[:4000]}"

        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 500,
                "temperature": 0.7,
                "topP": 0.9
            }
        })

        response = bedrock.invoke_model(
            modelId="amazon.titan-text-express-v1",
            body=body,
            contentType="application/json",
            accept="application/json"
        )
 response_body = json.loads(response['body'].read())
        summary = response_body["results"][0]["outputText"]

        conn = pymysql.connect(
            host=RDS_HOST,
            user=RDS_USER,
            password=RDS_PASSWORD,
            database=RDS_DB
        )
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS summaries (filename VARCHAR(255), summary TEXT)")
        cursor.execute("INSERT INTO summaries (filename, summary) VALUES (%s, %s)", (filename, summary))
        conn.commit()
        cursor.close()
        conn.close()

        return render_template_string(HTML_PAGE, summary=summary)

    except Exception as e:
        return f"Error: {str(e)}", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
