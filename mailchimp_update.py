# -*- coding: utf-8 -*-
"""
Created on Fri Sep 20 08:51:58 2019

Updates mailchimp lists by checking status first. 

@author: Elmer Smaling
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
import threading
from email.utils import parseaddr
import json
from hashlib import md5
import pandas as pd
from datetime import datetime
from mailchimp3 import MailChimp
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.environ.get("MAILCHIMP_API_KEY")
if not api_key:
    raise ValueError("MAILCHIMP_API_KEY not set in .env file")

# Load configuration from environment variables
config_update = os.environ.get("CONFIG_UPDATE", "False").lower() == "true"
config_paginate = int(os.environ.get("CONFIG_PAGINATE", "1000"))
debug_mode = os.environ.get("DEBUG_MODE", "False").lower() == "true"
listid = os.environ.get("MAILCHIMP_LIST_ID")
default_contact_type = os.environ.get("DEFAULT_CONTACT_TYPE", "Student")

# Load category configuration from environment variables
category = {
    'Kind of email': {
        'name': 'Kind of email',
        'id': os.environ.get("CATEGORY_KIND_OF_EMAIL_ID"),
        'Weekly': os.environ.get("CATEGORY_KIND_OF_EMAIL_WEEKLY"),
        'instant': os.environ.get("CATEGORY_KIND_OF_EMAIL_INSTANT"),
    },
    'Type': {
        'name': 'Type',
        'id': os.environ.get("CATEGORY_TYPE_ID"),
        'Student': os.environ.get("CATEGORY_TYPE_STUDENT"),
        'Employee': os.environ.get("CATEGORY_TYPE_EMPLOYEE"),
    }, 
    'Taal': {
        'name': 'Taal',
        'id': os.environ.get("CATEGORY_TAAL_ID"),
        'Nederlands': os.environ.get("CATEGORY_TAAL_NEDERLANDS"),
        'English': os.environ.get("CATEGORY_TAAL_ENGLISH"),
    },
}

client = MailChimp(mc_api=api_key, timeout=20.0)

class MailchimpUpdaterGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Mailchimp List Updater")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Data storage
        self.ingeschrevenen = [] # list from Excel file
        self.contact_list = [] # list of contacts to be processed
        self.fouten = [] # list of errors
        self.update_batch = [] # list of updates to be made
        self.create_batch = [] # list of new contacts to be created
        self.import_file_path = ""
        self.contact_type = default_contact_type
        self.processing = False
        self.debug_mode = debug_mode
        
        # Create GUI elements
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Header frame for title and logo
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)
        
        # File selection label in header
        ttk.Label(header_frame, text="Excel File Selection:", font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        
        # Logo placeholder in header (top right)
        self.logo_label = ttk.Label(header_frame, text="[LOGO]", font=('Arial', 8), foreground="gray")
        self.logo_label.grid(row=0, column=1, sticky=tk.E)
        
        # Load logo if available
        self.load_logo()
        
        # File selection section
        
        ttk.Button(main_frame, text="Select Excel File", command=self.select_file, padding=(5,5)).grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.file_label = ttk.Label(main_frame, text="No file selected", foreground="gray")
        self.file_label.grid(row=1, column=1, sticky=tk.W)
        
        # Contact type selection
        ttk.Label(main_frame, text="Contact Type:", font=('Arial', 12, 'bold')).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(20, 10))
        
        self.contact_type_var = tk.StringVar(value="Student")
        ttk.Radiobutton(main_frame, text="Students", variable=self.contact_type_var, value="Student").grid(row=3, column=0, sticky=tk.W)
        ttk.Radiobutton(main_frame, text="Employees", variable=self.contact_type_var, value="Employee").grid(row=3, column=1, sticky=tk.W)
        
        # Debug mode toggle
        ttk.Label(main_frame, text="Options:", font=('Arial', 12, 'bold')).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(20, 10))
        
        self.debug_mode_var = tk.BooleanVar(value=self.debug_mode)
        self.debug_checkbox = ttk.Checkbutton(main_frame, text="Debug Mode (Read-only, no API writes)", 
                                            variable=self.debug_mode_var, command=self.on_debug_toggle)
        self.debug_checkbox.grid(row=5, column=0, columnspan=2, sticky=tk.W)
        
        # Contact count display
        self.count_label = ttk.Label(main_frame, text="", font=('Arial', 10))
        self.count_label.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))
        style = ttk.Style()
        style.configure("Green.TButton", foreground="white", background="#4CAF50")

        # Process button
        self.process_button = ttk.Button(main_frame, text="Start Processing", command=self.start_processing, state=tk.DISABLED, padding=(10,10), style="Green.TButton")
        self.process_button.grid(row=7, column=0, columnspan=2, pady=(20, 10))
        
        # Progress section
        ttk.Label(main_frame, text="Progress:", font=('Arial', 12, 'bold')).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(20, 10))
        
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.progress_label = ttk.Label(main_frame, text="Ready to start")
        self.progress_label.grid(row=10, column=0, columnspan=2, sticky=tk.W)
        
        # Status and log section
        ttk.Label(main_frame, text="Status Log:", font=('Arial', 12, 'bold')).grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=(20, 10))
        
        # Text widget with scrollbar for status log
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=12, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(12, weight=1)
        
        self.log_text = tk.Text(log_frame, height=15, width=80, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Batch status section
        self.status_frame = ttk.Frame(main_frame)
        self.status_frame.grid(row=13, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.check_status_button = ttk.Button(self.status_frame, text="Check Batch Status", command=self.check_batch_status, state=tk.DISABLED)
        self.check_status_button.grid(row=0, column=0, padx=(0, 10))
        
        self.status_label = ttk.Label(self.status_frame, text="")
        self.status_label.grid(row=0, column=1, sticky=tk.W)
    
    def load_logo(self):
        """Load and display logo image if available"""
        try:
            if not PIL_AVAILABLE:
                # Try to load with tkinter's built-in PhotoImage (supports GIF/PPM/PGM)
                logo_files = ['logo.gif', 'logo.ppm', 'logo.pgm']
                logo_path = None
                
                for logo_file in logo_files:
                    if os.path.exists(logo_file):
                        logo_path = logo_file
                        break
                
                if logo_path:
                    self.logo_image = tk.PhotoImage(file=logo_path)
                    # Subsample to resize (basic resizing)
                    self.logo_image = self.logo_image.subsample(2, 2)  # Reduce by half
                    self.logo_label.config(image=self.logo_image, text="")
                    #self.log_message(f"Logo loaded: {logo_path}")
                else:
                    self.logo_label.config(text="[LOGO]")
                return
            
            # PIL is available - support more formats
            logo_files = ['logo.png', 'logo.jpg', 'logo.jpeg', 'logo.gif', 'logo.bmp']
            logo_path = None
            
            for logo_file in logo_files:
                if os.path.exists(logo_file):
                    logo_path = logo_file
                    self.log_message(f"Found logo file: {logo_file}")
                    break
            
            if logo_path:
                # Load and resize the image
                image = Image.open(logo_path)
                # Resize to fit nicely in the header (max height 40px)
                image.thumbnail((100, 40), Image.Resampling.LANCZOS)
                
                # Convert to PhotoImage
                self.logo_image = ImageTk.PhotoImage(image)
                
                # Update the logo label
                self.logo_label.config(image=self.logo_image, text="")
                if hasattr(self, 'log_message'):
                    self.log_message(f"Logo loaded: {logo_path}")
            else:
                # Keep placeholder text if no logo found
                self.logo_label.config(text="[LOGO]")
                
        except Exception as e:
            # If PIL is not available or other error, show fallback
            self.logo_label.config(text="[LOGO]")
            if hasattr(self, 'log_message'):
                self.log_message(f"Logo loading failed: {str(e)}")
    
    def on_debug_toggle(self):
        """Handle debug mode toggle"""
        self.debug_mode = self.debug_mode_var.get()
        if self.debug_mode:
            self.log_message("🐛 DEBUG MODE ENABLED - No API writes will be performed")
            self.process_button.config(text="Start Processing (DEBUG)")
        else:
            self.log_message("✅ Debug mode disabled - Normal operation")
            self.process_button.config(text="Start Processing")
        
    def select_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        
        if file_path:
            self.import_file_path = file_path
            filename = file_path.split('/')[-1].split('\\')[-1]  # Get just the filename
            self.file_label.config(text=f"Selected: {filename}", foreground="black")
            
            # Try to load the file and count contacts
            try:
                import pandas as pd
                self.ingeschrevenen = pd.read_excel(file_path)
                count = len(self.ingeschrevenen)
                self.count_label.config(text=f"Found {count} contacts in the file")
                self.process_button.config(state=tk.NORMAL)
                self.log_message(f"Loaded Excel file: {filename}")
                self.log_message(f"Found {count} contacts")
            except Exception as e:
                messagebox.showerror("Error", f"Error loading Excel file: {str(e)}")
                self.log_message(f"Error loading file: {str(e)}")
    
    def log_message(self, message):
        """Add a message to the status log"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def start_processing(self):
        """Start the processing in a separate thread to avoid blocking the GUI"""
        if self.processing:
            return
            
        if not self.import_file_path or len(self.ingeschrevenen) == 0:
            messagebox.showerror("Error", "Please select a valid Excel file first")
            return
        
        self.processing = True
        self.process_button.config(state=tk.DISABLED)
        self.contact_type = self.contact_type_var.get()
        self.debug_mode = self.debug_mode_var.get()
        
        # Clear previous results
        self.fouten = []
        self.update_batch = []
        self.create_batch = []
        
        # Start processing in a separate thread
        thread = threading.Thread(target=self.process_contacts)
        thread.daemon = True
        thread.start()
    
    def process_contacts(self):
        """Process contacts (runs in separate thread)"""
        try:
            aantal = len(self.ingeschrevenen)
            mode_text = "DEBUG MODE" if self.debug_mode else "PRODUCTION MODE"
            self.log_message(f"🚀 Starting to process {aantal} contacts as {self.contact_type}s - {mode_text}")
            
            if self.debug_mode:
                self.log_message("🐛 DEBUG: API writes are DISABLED - only read operations will be performed")
                self.log_message(f"🐛 DEBUG: Configuration - Update: {config_update}, List ID: {listid}")
                self.log_message(f"🐛 DEBUG: Categories loaded: {len(category)} categories available")
            
            # Reset progress
            self.progress['maximum'] = aantal
            self.progress['value'] = 0
            
            cnt = 0
            update_lid = 0
            nieuw_lid = 0
            starttijd = datetime.now()
            
            for index, contact in self.ingeschrevenen.iterrows(): # Iterate excel file
                # Clean and format current contact
                contact = self.cleancontact(contact, index)
                if not contact:
                    if self.debug_mode:
                        self.log_message(f"🐛 DEBUG: Skipped invalid contact at index {index}")
                    cnt += 1
                    continue
                
                cnt += 1
                
                # Update progress
                self.progress['value'] = cnt
                progress_text = f"Processing {cnt}/{aantal} - {contact['roepnaam']} {contact['achternaam']}"
                self.progress_label.config(text=progress_text)
                
                # Log current contact
                if self.debug_mode:
                    self.log_message(f"🐛 DEBUG: Processing contact {cnt}/{aantal}: {contact['roepnaam']} {contact['achternaam']} ({contact['e-mailadres']})")

                # Process contact with Mailchimp
                email_address = contact['e-mailadres']
                md5hash = md5(email_address.lower().encode('utf-8')).hexdigest()
                
                if self.debug_mode:
                    self.log_message(f"🐛 DEBUG: Email: {email_address}, MD5 hash: {md5hash}")
                
                hit = ""
                nieuwe = False
                
                if self.debug_mode:
                    self.log_message(f"🐛 DEBUG: Checking if member exists in Mailchimp...")
                
                # check if member exists in Mailchimp
                try:
                    hit = client.lists.members.get(list_id=listid, subscriber_hash=md5hash, fields="status,merge_fields.FNAME,merge_fields.LNAME,interests")
                    if self.debug_mode:
                        self.log_message(f"🐛 DEBUG: Found existing member - Status: {hit.get('status', 'unknown')}, Name: {hit.get('merge_fields', {}).get('FNAME', '')  } {hit.get('merge_fields', {}).get('LNAME', '')}")
                except Exception as e:
                    nieuwe = True
                    if self.debug_mode:
                        self.log_message(f"🐛 DEBUG: Member not found in list (will be created) - Error: {str(e)[:100]}")
                
                if nieuwe:  # New member

                    # prepare member data for insertion
                    memberdata = {
                        'email_address': email_address,
                        'status': 'subscribed',
                        'merge_fields': {
                            'FNAME': contact['roepnaam'],
                            'LNAME': contact['achternaam'],
                            'TYPE': self.contact_type,
                        },
                        'interests': {
                            category['Type'][self.contact_type]: True,
                            category['Kind of email']['Weekly']: True,
                            category['Taal']['Nederlands']: True,
                        },
                    }
                    
                    if self.debug_mode:
                        self.log_message(f"🐛 DEBUG: Would CREATE new member with data: {json.dumps(memberdata, indent=2)}")
                        self.log_message(f"🐛 DEBUG: Operation would be POST to /lists/{listid}/members/")
                    else:
                        self.log_message(f"CREATE: {contact['roepnaam']} {contact['achternaam']} ({contact['e-mailadres']})")

                    operation_item = {
                        "method": "POST",
                        "path": "/lists/" + listid + "/members/",
                        "operation_id": "create_batch",
                        "body": json.dumps(memberdata)
                    }
                    
                    self.create_batch.append(operation_item)
                    nieuw_lid += 1
                    
                else:  # Existing member

                    if config_update == False:
                        if self.debug_mode:
                            self.log_message(f"🐛 DEBUG: Skipping update for existing member (CONFIG_UPDATE=False)")
                        continue
                    
                    if self.debug_mode:
                        self.log_message(f"🐛 DEBUG: Updating existing member...")
                    
                    # Save names from Excel file
                    original_fname = hit['merge_fields'].get('FNAME', '')
                    original_lname = hit['merge_fields'].get('LNAME', '')
                    
                    # Check if there is a first or last name in the response from Mailchimp
                    # If so, keep the name from Mailchimp
                    if original_lname is not None: 
                        contact['achternaam'] = original_lname
                    if original_fname is not None:
                        contact['roepnaam'] = original_fname
                    
                    if original_fname != hit['merge_fields'].get('FNAME', '') and original_lname != hit['merge_fields'].get('LNAME', ''):
                        self.log_message(f"UPDATE: New name for {original_fname} {original_lname}: {contact['roepnaam']} {contact['achternaam']}")
                    else:
                        self.log_message(f"UPDATE: Rejected input from Excel: {contact['roepnaam']} {contact['achternaam']} -> Keeping {original_fname} {original_lname} from Mailchimp")
                        
                        
                    engels = category['Taal']['English']
                    nederlands = category['Taal']['Nederlands']
                    if isinstance(hit['interests'][engels], bool):
                        if not hit['interests'][engels]:
                            taalset = nederlands
                        else:
                            taalset = engels
                    
                    if self.debug_mode:
                        current_lang = "English" if taalset == engels else "Nederlands"
                        self.log_message(f"🐛 DEBUG: Language preference: {current_lang} (ID: {taalset})")
                    
                    memberdata = {
                        'email_address': email_address,
                        'merge_fields': {
                            'FNAME': contact['roepnaam'],
                            'LNAME': contact['achternaam'],
                            'TYPE': self.contact_type,
                        },
                        'interests': {
                            category['Type'][self.contact_type]: True,
                            taalset: True,
                        },
                    }
                    
                    if self.debug_mode:
                        self.log_message(f"🐛 DEBUG: Would UPDATE existing member with data: {json.dumps(memberdata, indent=2)}")
                        self.log_message(f"🐛 DEBUG: Operation would be PATCH to /lists/{listid}/members/{md5hash}")
                    
                    operation_item = {
                        "method": "PATCH",
                        "path": "/lists/" + listid + "/members/" + md5hash,
                        "operation_id": "update_batch",
                        "body": json.dumps(memberdata)
                    }
                    
                    self.update_batch.append(operation_item)
                    update_lid += 1
                
                # Update status
                self.root.after(0, lambda: self.progress_label.config(
                    text=f"Processed {cnt}/{aantal} - {nieuw_lid} new, {update_lid} updates - Time remaining: {self.formatTimeDelta(starttijd, cnt/aantal)}"
                ))
            
            # Show errors if any
            if self.fouten:
                self.log_message("\n--- Errors and Warnings ---")
                for fout in self.fouten:
                    self.log_message(fout)
            
            # Execute batch operations
            self.create_id = None
            self.update_id = None
            
            if self.debug_mode:
                # In debug mode, don't actually execute API writes
                self.log_message("🐛 DEBUG: ========== BATCH OPERATIONS SUMMARY ==========")
                if nieuw_lid > 0:
                    self.log_message(f"🐛 DEBUG: Would create {nieuw_lid} new members")
                    self.log_message(f"🐛 DEBUG: Create batch contains {len(self.create_batch)} operations")
                if update_lid > 0:
                    self.log_message(f"🐛 DEBUG: Would update {update_lid} existing members")
                    self.log_message(f"🐛 DEBUG: Update batch contains {len(self.update_batch)} operations")
                self.log_message("🐛 DEBUG: NO API WRITES PERFORMED (Debug mode enabled)")
                self.log_message("🐛 DEBUG: ===============================================")
            else:
                # Normal operation - execute batch operations
                if nieuw_lid > 0:
                    self.log_message(f"Creating batch operation for {nieuw_lid} new members...")
                    handle = client.batch_operations.create(data={"operations": self.create_batch})
                    self.create_id = handle['id']
                    self.log_message(f"Created batch operation ID: {self.create_id}")
                
                if update_lid > 0:
                    self.log_message(f"Creating batch operation for {update_lid} member updates...")
                    handle = client.batch_operations.create(data={"operations": self.update_batch})
                    self.update_id = handle['id']
                    self.log_message(f"Update batch operation ID: {self.update_id}")
            
            completion_message = "\nProcessing completed!"
            if self.debug_mode:
                completion_message += " (DEBUG MODE - No changes made to Mailchimp)"
            else:
                completion_message += " You can now check the batch status."
                completion_message += "\nLarge batches may take some time to process on Mailchimp's end."
            
            self.log_message(completion_message)
            
            # Enable status checking only if not in debug mode and there are actual batches
            if not self.debug_mode and (nieuw_lid > 0 or update_lid > 0):
                self.root.after(0, lambda: self.check_status_button.config(state=tk.NORMAL))
            
        except Exception as e:
            self.log_message(f"Error during processing: {str(e)}")
            messagebox.showerror("Processing Error", f"An error occurred: {str(e)}")
        
        finally:
            self.processing = False
            self.root.after(0, lambda: self.process_button.config(state=tk.NORMAL))
    
    def safe_str(self, value):
        """Safely convert value to string, handling NaN values from pandas"""
        if value is None:
            return ""
        str_val = str(value).strip()
        if str_val.lower() in ['nan', 'none', 'null']:
            return ""
        return str_val
    
    def cleancontact(self, contact, index):
        """Clean and validate contact data"""
        # Convert to lowercase for future-proofing and handle NaN values
        contact = {k.lower(): self.safe_str(v) for k, v in contact.items()}
        
        # Handle aliases and English names
        if 'prefix' in contact: contact['voorvoegsels'] = contact['prefix']
        if 'first name' in contact: contact['roepnaam'] = contact['first name']
        if 'last name' in contact: contact['achternaam'] = contact['last name']
        if 'name' in contact: contact['achternaam'] = contact['name']
        
        if 'voorvoegsel' in contact: contact['voorvoegsels'] = contact['voorvoegsel']
        if 'voornaam' in contact:
            contact['roepnaam'] = contact['voornaam']
        else:
            if 'voorletters' in contact: contact['roepnaam'] = contact['voorletters']
        if 'naam' in contact: contact['achternaam'] = contact['naam']
        
        # Find email field and clean it
        email_value = next((v for k, v in contact.items() if 'email' in k.lower().replace('-', '')), None)
        contact['e-mailadres'] = self.safe_str(email_value) if email_value else ""
        
        # Check for missing names (already cleaned by safe_str method)
        if not contact.get('roepnaam'):
            contact['roepnaam'] = ""
            self.fouten.append('Warning: First name missing for ' + str(contact['e-mailadres']))
            
        if not contact.get('achternaam'):
            contact['achternaam'] = ""
            self.fouten.append('Warning: Last name missing for ' + str(contact['e-mailadres']))
            
        # Handle voorvoegsels (prefixes) - already cleaned by safe_str
        if contact.get('voorvoegsels'):
            contact['achternaam'] = contact['voorvoegsels'] + " " + contact['achternaam']
        if not self.is_valid_email(str(contact['e-mailadres'])):
            self.fouten.append("Error: Invalid email address (index = " + str(index) + ")")
            return False
        
        return contact
    
    def is_valid_email(self, email):
        """Validate email address using robust regex pattern"""
        import re
        
        if not email or not isinstance(email, str):
            return False
        
        email = email.strip().lower()
        
        # Comprehensive regex pattern for email validation
        # Based on RFC 5322 specification but practical for real-world use
        pattern = r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        
        return re.match(pattern, email) is not None
    
    def formatTimeDelta(self, starttijd, perc):
        """Format time remaining estimate"""
        if perc <= 0:
            return "Calculating..."
        time_passed = datetime.now() - starttijd
        total_time = time_passed / perc
        time_remaining = total_time - time_passed
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return '{:02}:{:02}:{:02}'.format(int(hours), int(minutes), int(seconds))
    
    def check_batch_status(self):
        """Check the status of batch operations"""
        if self.debug_mode:
            self.log_message("🐛 DEBUG: Batch status check not available in debug mode (no batches were created)")
            self.status_label.config(text="Debug mode - no batches created")
            return
            
        try:
            status_messages = []
            
            if hasattr(self, 'create_id') and self.create_id:
                create_check = client.batch_operations.get(batch_id=self.create_id)
                status_messages.append(f"New members batch: {create_check['status']}")
                self.log_message(f"New members batch status: {create_check['status']}")
            
            if hasattr(self, 'update_id') and self.update_id:
                update_check = client.batch_operations.get(batch_id=self.update_id)
                status_messages.append(f"Updates batch: {update_check['status']}")
                self.log_message(f"Updates batch status: {update_check['status']}")
            
            if status_messages:
                self.status_label.config(text=" | ".join(status_messages))
            else:
                self.status_label.config(text="No batch operations found")
                
        except Exception as e:
            self.log_message(f"Error checking batch status: {str(e)}")
            messagebox.showerror("Status Check Error", f"Error checking batch status: {str(e)}")
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

# Initialize the GUI application
if __name__ == "__main__":
    app = MailchimpUpdaterGUI()
    app.run()

        