# **Group 5 - Softsec-shop Setup Guide**

*For full documentation, please refer to our Notion workspace:*
**[https://www.notion.so/Secure-Software-Application-Project-Team-5-29daaa8c79d7806887c6f590ae937ee3](https://www.notion.so/Secure-Software-Application-Project-Team-5-29daaa8c79d7806887c6f590ae937ee3)**

---

This guide contains the full setup instructions for running **Softsec-shop**.
Please **follow the steps in order**.

---

## **1. Make the HTTPS Certificate**

Set up a valid HTTPS certificate for local or production use.

---

## **2. Generate PayPal API Key, Secret, and Sandbox Account**

### **Getting Started with PayPal**

1. **Create a PayPal Developer Account**
   [https://developer.paypal.com/home/](https://developer.paypal.com/home/)

2. **Set Up API Credentials**

   * Go to **Dashboard → Apps & Credentials**
     [https://developer.paypal.com/dashboard/applications/sandbox](https://developer.paypal.com/dashboard/applications/sandbox)
   * Click **Create App**
   * Obtain your **PayPal Client ID** and **Secret Key**
   * Add them to your `.env` file

3. **Create PayPal Sandbox Account**

   * Go to **Testing Tools → Sandbox Accounts**
     [https://developer.paypal.com/dashboard/accounts](https://developer.paypal.com/dashboard/accounts)
   * Click **Create Account**
   * Use this account to log in when testing PayPal payments
   * You may also use the provided sandbox credentials (if applicable)

---

## **3. Generate DHL API Key**

1. Go to the DHL Developer Portal:
   [https://developer.dhl.com](https://developer.dhl.com)
2. Create an account or log in
3. Navigate to **My Apps** → **Create App**
4. Enable the API your project requires (e.g., DHL Shipment Tracking or DHL Express API)
5. Copy the **API Key / Client ID / Secret** into your `.env` file

---

## **4. Fill in the `.env` File**

Add the following into your `.env`:

* PayPal Client ID + Secret
* DHL API Key
* DHL Username + Password

**DHL Sandbox Credentials (from docs):**

```
Username: user-valid
Password: SandboxPasswort2023!
```

---

## **5. Rebuild the Docker Container**

Run this command to load the `.env` file and install any new packages:

```bash
docker compose up -d --build
```

---

## **6. Migrate the Database**

Follow these steps **inside your database tool and container**.

### **Step A: Delete Existing Database**

1. Inside your DB UI, right-click the existing DB name → **Delete**
   *(screenshot reference)*

### **Step B: Create New Database**

1. Right-click **Databases** → **Create New Database**
2. Use this name:

```
flaskshop
```

### **Step C: Enter the Container**

```bash
docker compose exec web sh
```

### **Step D: Run Migration Commands**

1. **Create DB structure**

```bash
python -m flask createdb
```

2. **Generate random data**

```bash
python -m flask seed
```

(If `seed` is not available, use the correct command provided by the project.)

---

## **7. Rebuild the Frontend**

1. Go to the frontend folder:

```bash
cd frontend
```

2. Build the frontend:

```bash
npm run build
```

---

## **8. Access the Application**

You can now open Flaskshop at:

```
https://127.0.0.1
```

---

If you'd like, I can turn this into a downloadable `.md` file using a file generator — just say **“export as file”**.
