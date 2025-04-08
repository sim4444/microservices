FROM python:3


# Create an application directory
RUN mkdir /app

# Copy requirements file to the container
COPY ./requirements.txt /app/requirements.txt

# Set working directory
WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files to the container
COPY . /app

# Ensure the logs directory exists and has full permissions
RUN mkdir -p /app/logs/analyzer && chmod -R 777 /app/logs 

# Allow non-root user
RUN chown -R nobody:nogroup /app
USER nobody

# Expose the service port
EXPOSE 8200

# Entrypoint and command to start the service
ENTRYPOINT ["python3"]
CMD ["app.py"]
