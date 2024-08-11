import os

bind = "0.0.0.0:" + os.getenv("PORT", "5000")
workers = 2
