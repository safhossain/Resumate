import sys
from jinja2 import Environment, FileSystemLoader
from pdflatex import PDFLaTeX
from dotenv import load_dotenv, dotenv_values

load_dotenv()

ctx = dotenv_values(".env")

def main():
    return 0


if __name__ == '__main__':
    main()