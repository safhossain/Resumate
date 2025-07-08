import os
from dotenv import load_dotenv

load_dotenv()

my_name=os.getenv("NAME")
my_phone=os.getenv("PHONE_NUMBER")
my_email=os.getenv("EMAIL")
my_github=os.getenv("GITHUB")

print(my_name)
print(my_phone)
print(my_github)
print(my_email)