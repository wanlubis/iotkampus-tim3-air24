#!/usr/bin/env bash
echo "Generating Mosquitto password file..."
docker run --rm -v "$(pwd)/config:/cfg" eclipse-mosquitto:2 mosquitto_passwd -b /cfg/passwordfile air24_user air24_password123
echo "Done! User 'air24_user' configured."
