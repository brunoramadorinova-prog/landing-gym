#!/bin/bash
pip install gunicorn flask flask-cors psycopg2-binary bcrypt google-auth requests mercadopago pyjwt
exec gunicorn main:app --bind 0.0.0.0:$PORT --workers 1