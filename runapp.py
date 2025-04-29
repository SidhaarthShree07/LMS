import subprocess
import platform
# List of libraries to download
libraries = [
    "alembic==1.13.1",
    "antiorm==1.2.1",
    "azure-cognitiveservices-speech==1.36.0",
    "blinker==1.7.0",
    "certifi==2024.2.2",
    "charset-normalizer==3.3.2",
    "click==8.1.7",
    "colorama==0.4.6",
    "contourpy==1.2.0",
    "cycler==0.12.1",
    "db==0.1.1",
    "db-sqlite3==0.0.1",
    "Flask==3.0.2",
    "Flask-Login==0.6.3",
    "Flask-Migrate==4.0.7",
    "Flask-SQLAlchemy==3.1.1",
    "fonttools==4.50.0",
    "greenlet==3.0.3",
    "gTTS==2.5.1",
    "idna==3.6",
    "itsdangerous==2.1.2",
    "Jinja2==3.1.3",
    "kiwisolver==1.4.5",
    "Mako==1.3.2",
    "MarkupSafe==2.1.5",
    "matplotlib==3.8.3",
    "numpy==1.26.4",
    "packaging==24.0",
    "pandas==2.2.1",
    "pillow==10.2.0",
    "PyMuPDF==1.23.26",
    "PyMuPDFb==1.23.22",
    "pyparsing==3.1.2",
    "python-dateutil==2.9.0.post0",
    "pytz==2024.1",
    "requests==2.31.0",
    "six==1.16.0",
    "SQLAlchemy==2.0.27",
    "typing_extensions==4.9.0",
    "tzdata==2024.1",
    "urllib3==2.2.1",
    "Werkzeug==3.0.1",
    "zip-files==0.4.1"
]

# Create a virtual environment
subprocess.run(["python", "-m", "venv", "myenv"], check=True)

# Activate the virtual environment
activate_script = "myenv\\Scripts\\activate" if platform.system() == "Windows" else "source myenv/bin/activate"
subprocess.run(activate_script, shell=True, check=True)

# Install libraries in the virtual environment
for library in libraries:
    subprocess.run(["pip", "install", library], check=True)

#It will take few minutes