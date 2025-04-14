import mysql.connector
import requests
import time  
import google.generativeai as genai

# Configure Gemini API
genai.configure(api_key="Your Api Keys")
model = genai.GenerativeModel("gemini-2.0-flash")

# Connect to MySQL
connector = mysql.connector.connect(host='localhost', user='root', password='root@123', database='medicineapi')
cursor = connector.cursor()

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS symptoms (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symptom_name VARCHAR(255) NOT NULL UNIQUE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS symptom_causes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    symptom_id INT,
    cause TEXT,
    FOREIGN KEY (symptom_id) REFERENCES symptoms(id) ON DELETE CASCADE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS medicine (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_name VARCHAR(255) NOT NULL,
    symptom_id INT,
    FOREIGN KEY (symptom_id) REFERENCES symptoms(id) ON DELETE CASCADE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS purpose (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id INT,
    purpose_text TEXT,
    FOREIGN KEY (medicine_id) REFERENCES medicine(id) ON DELETE CASCADE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS warning (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_id INT,
    warning_text TEXT,
    FOREIGN KEY (medicine_id) REFERENCES medicine(id) ON DELETE CASCADE
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS allergy (
    id INT AUTO_INCREMENT PRIMARY KEY,
    medicine_name VARCHAR(255) NOT NULL,
    allergy_warning TEXT
);
""")

connector.commit()

def main():
    symptom_list = []

    while True:
        user_choice = input("Enter symptom? (y/n): ").strip().lower()
        if user_choice == 'y':
            user_symptom = input("Enter the symptom: ").strip().lower()
            if user_symptom and user_symptom not in symptom_list:
                symptom_list.append(user_symptom)
        elif user_choice == 'n':
            break

    if not symptom_list:
        print("No symptoms entered.")
        return

    formatted_symptoms = ", ".join(symptom_list)
    
    if check_existing_data(formatted_symptoms):
        print(f"\nData already exists in the database: {formatted_symptoms}\n")
        show_results(formatted_symptoms)
    else:
        print("\nFetching data from API...\n")
        causes(symptom_list)
    checkWeather()

def fetch_fda_data(symptom):
    search_query = f'active_ingredient:"{symptom}"'
    url = f'https://api.fda.gov/drug/label.json?search={search_query}&limit=5'
    
    time.sleep(1)
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        for item in data.get("results", []):
            brand_name = ", ".join(item.get("package_label_principal_display_panel", ["No brand name available"]))
            purpose = ", ".join(item.get("purpose", ["No purpose available"]))
            warnings = ", ".join(item.get("warnings", ["No warnings available"]))
            
            check_symptoms(brand_name, purpose, warnings, symptom)
    else:
        print(f"Error: {response.status_code}, {response.text}")

def check_existing_data(symptom_combination):
    query = "SELECT COUNT(*) FROM symptoms WHERE symptom_name = %s"
    cursor.execute(query, (symptom_combination,))
    result = cursor.fetchone()
    return result[0] > 0  

def causes(symptom_list):
    prompt = f"""Given the following symptom(s):

    {", ".join(symptom_list)}

    Identify 2-3 common potential causes or conditions that could be associated with these symptoms. 

    Focus on common, non-life-threatening possibilities. Do not provide medical diagnoses or treatment recommendations.

    If the symptom is too vague or requires a medical professional for proper evaluation, state "Further medical evaluation is required."

    Provide the causes or conditions as a comma-separated list.
    """

    time.sleep(1)
    response = model.generate_content(prompt)
    causes = response.text.strip()

    print("\nCauses received from AI:", causes)

    if "there is no" in causes.lower():
        print("Skipping due to lack of relevant data.")
        return

    push_into_sql_symptoms(symptom_list, causes)

def check_symptoms(brand_name, purpose, warnings, symptom_name):
    prompt = f"""Based on the following drug information:

    Purpose: {purpose}
    Warnings: {warnings}

    Suggest 1 commonly known over-the-counter (OTC) brand name that treats the given condition. 
    - If multiple brands exist, choose the most widely known one.
    - If no relevant brand exists, return "No known OTC brand available."

    Provide only the brand name in your response, nothing else.
    """

    try:
        time.sleep(1)
        response = model.generate_content(prompt)
        brand_suggestion = response.text.strip()

        if "no known" in brand_suggestion.lower():
            print("Skipping due to lack of brand name info.")
            return

        print(f"\nSuggested Brand Name: {brand_suggestion}")
        push_into_sql_medicine(brand_suggestion, purpose, warnings, symptom_name)

    except Exception as e:
        print(f"AI Error: {e}")

def push_into_sql_symptoms(symptom_list, causes):
    formatted_symptoms = ", ".join(symptom_list)

    if not check_existing_data(formatted_symptoms):
        cursor.execute("INSERT INTO symptoms (symptom_name) VALUES (%s)", (formatted_symptoms,))
        connector.commit()

        cursor.execute("SELECT id FROM symptoms WHERE symptom_name = %s", (formatted_symptoms,))
        result = cursor.fetchone()
        if not result:
            print(f"Failed to fetch ID for symptom: {formatted_symptoms}")
            return
        symptom_id = result[0]

        causes_list = [cause.strip() for cause in causes.split(",")]
        for cause in causes_list:
            cursor.execute("INSERT INTO symptom_causes (symptom_id, cause) VALUES (%s, %s)", (symptom_id, cause))
        connector.commit()

        fetch_fda_data(formatted_symptoms)
    else:
        print(f"Skipped (Already Exists): {formatted_symptoms}")

def summarize_warnings(warnings_text):
    prompt = f"""Summarize the following medical warnings in 3 key points. Keep it concise and readable:

    {warnings_text}
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def summarize_purpose(purpose_text):
    prompt = f"""Summarize the following medicine purpose in 2 key points. Keep it brief and to the point:

    {purpose_text}
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def push_into_sql_medicine(brand_name, purpose, warnings, symptom_name):
    summarized_warnings = summarize_warnings(warnings)
    summarized_purpose = summarize_purpose(purpose)

    cursor.execute("SELECT id FROM symptoms WHERE symptom_name = %s", (symptom_name,))
    result = cursor.fetchone()

    if result:
        symptom_id = result[0]
    else:
        print(f"Symptom '{symptom_name}' not found, cannot add medicine.")
        return

    cursor.execute("SELECT id FROM medicine WHERE medicine_name = %s AND symptom_id = %s", (brand_name, symptom_id))
    result = cursor.fetchone()
    
    if result:
        print(f"Skipped (Already Exists for this symptom): {brand_name}")
        medicine_id = result[0]
    else:
        cursor.execute("INSERT INTO medicine (medicine_name, symptom_id) VALUES (%s, %s)", (brand_name, symptom_id))
        connector.commit()
        medicine_id = cursor.lastrowid

    # Insert purpose and warning
    cursor.execute("INSERT INTO purpose (medicine_id, purpose_text) VALUES (%s, %s)", (medicine_id, summarized_purpose))
    cursor.execute("INSERT INTO warning (medicine_id, warning_text) VALUES (%s, %s)", (medicine_id, summarized_warnings))
    connector.commit()

    push_into_sql_allergy(brand_name)
    show_results(symptom_name)


def generate_allergy_warning(medicine_name):
    prompt = f"""Identify common allergies that could react negatively to the following medicine:

    Medicine: {medicine_name}

    Provide a brief warning mentioning the key allergens to avoid.
    """
    response = model.generate_content(prompt)
    return response.text.strip()

def push_into_sql_allergy(medicine_name):
    allergy_warning = generate_allergy_warning(medicine_name)
    cursor.execute("INSERT INTO allergy (medicine_name, allergy_warning) VALUES (%s, %s)", (medicine_name, allergy_warning))
    connector.commit()

def show_results(symptom_name):
    cursor.execute("SELECT id FROM symptoms WHERE symptom_name = %s", (symptom_name,))
    result = cursor.fetchone()

    if result:
        symptom_id = result[0]
        cursor.execute("SELECT id, medicine_name FROM medicine WHERE symptom_id = %s", (symptom_id,))
        medicines = cursor.fetchall()

        if medicines:
            print("\nMedicines for", symptom_name, ":")
            for med_id, med_name in medicines:
                # Get purpose and warning separately
                cursor.execute("SELECT purpose_text FROM purpose WHERE medicine_id = %s", (med_id,))
                purpose = cursor.fetchone()
                cursor.execute("SELECT warning_text FROM warning WHERE medicine_id = %s", (med_id,))
                warning = cursor.fetchone()
                cursor.execute("SELECT allergy_warning FROM allergy WHERE medicine_name = %s", (med_name,))
                allergy_result = cursor.fetchone()

                purpose_text = purpose[0] if purpose else "No purpose info"
                warning_text = warning[0] if warning else "No warning info"
                allergy_text = allergy_result[0] if allergy_result else "No allergy warning available"

                print(f"  : {med_name}\n  Purpose: {purpose_text}\n  Warning: {warning_text}\n  Allergy Warning: {allergy_text}\n")
        else:
            print(f"No medicine found for symptom: {symptom_name}")
    else:
        print(f"Symptom '{symptom_name}' not found in the database.")

def checkWeather():
    city = input("Enter the city please: ")
    api_key = 'You Api Keys'

    geocode_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={api_key}"
    geocode_response = requests.get(geocode_url)

    if geocode_response.status_code == 200:
        geo_data = geocode_response.json()
        if not geo_data:
            print("City not found. Please enter a valid city name.")
            return

        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]

        aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
        aqi_response = requests.get(aqi_url)

        if aqi_response.status_code == 200:
            aqi_data = aqi_response.json()
            aqi_value = aqi_data["list"][0]["main"]["aqi"] * 50

            print(f"AQI for {city}: {aqi_value}")

            message = get_aqi_message(aqi_value)
            print(f"Advice: {message}")
        else:
            print("Failed to fetch AQI data.")
    else:
        print("Failed to fetch location data.")

def get_aqi_message(aqi_value):
    query = "SELECT message FROM aqi WHERE min_aqi <= %s AND max_aqi >= %s"
    cursor.execute(query, (aqi_value, aqi_value))
    result = cursor.fetchone()
    return result[0] if result else "No AQI advice available."

if __name__ == "__main__":
    main()