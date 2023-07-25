import sqlite3
import tkinter as tk
import tkinter.ttk as ttk
import tkinter.messagebox as messagebox
import threading
import os
import datetime
from configparser import ConfigParser

from func.utils import calculate_next_month_day, calculate_time_remaining, get_key, update_config_from_env
from func.execute_query import execute_sql_query
from func.export_to_excel import export_to_excel
from func.send_email import send_email_with_attachment
from watchdog.observers import Observer
from PIL import Image, ImageTk

database_path = os.path.join(os.path.dirname(__file__), 'DB_TEST.sqlite3')
# Update the configuration retrieval with default values if not found
objet_mail = get_key('objet', default_value='Mon Mail Objet')
message_mail = get_key('message', default_value='Mon Message')

smtp = {
    'server': get_key('smtp_serveur', default_value='mail.inviso-group.com'),
    'username': get_key('smtp_username', default_value='muriel.raharison@inviso-group.com'),
    'password': get_key('smtp_password', default_value='DzczeHgosm'),
    'port': int(get_key('smtp_port', default_value=587))
}


def watch_get_key_file():
    calculate_time_remaining()
    calculate_next_month_day()
    update_time_remaining_label()
    update_history_table()
    update_label_periodically()
    event_handler = update_config_from_env()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()


def create_historique_table():
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Historique (
                email TEXT,
                objet TEXT,
                message TEXT,
                data TEXT,
                date DATE,
                time TIME,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        # Handle the error if the table creation fails
        messagebox.showerror("Error", f"An error occurred while creating the 'Historique' table: {str(e)}")


def data_sent_email():
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT Societes.name, Societes.server, Societes.username, Societes.password, Emails.email
            FROM EmailSociete
            INNER JOIN Societes ON EmailSociete.id_societe = Societes.id
            INNER JOIN Emails ON EmailSociete.id_email = Emails.id
        """)
        rows = cursor.fetchall()
        print(rows)

        for row in rows:
            # Traitez chaque ligne de données ici
            name, server, username, password, email = row
            base = {
                'server': server,
                'database': name,
                'username': username,
                'password': password
            }

            df = execute_sql_query(base)
            filename = export_to_excel(df=df, objet=name)
            send_email_with_attachment(data=name, filename=filename, recipients=email, smtp=smtp,
                                       local_db=database_path, objet_mail=objet_mail,
                                       message_mail=message_mail)

        cursor.close()
        conn.close()

        return rows

    except Exception as e:
        # You can customize the error message as per your requirement
        messagebox.showerror("Error", f"An error occurred sending mail: {str(e)} ")


def execute_script():
    try:
        create_historique_table()
        data_sent_email()
        update_time_remaining_label()
    except Exception as e:
        # You can customize the error message as per your requirement
        messagebox.showerror("Error", f"An error occured : {str(e)} ")


def format_time(days, hours, minutes, seconds):
    return f"{days} jours, {hours:02d} heures, {minutes:02d} minutes, {seconds:02d} secondes"


def update_history_table():
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        # Fetch data from the 'Historique' table in descending order based on 'date' and 'time'
        cursor.execute("""
            SELECT date, time, objet, email, message, data, status FROM Historique
            ORDER BY date DESC, time DESC
        """)
        rows = cursor.fetchall()

        history_tree.delete(*history_tree.get_children())

        for row in rows:
            # Rearrange the order of data to match the column order (Date, Heure, Email, Donnée)
            data_in_order = [row[0], row[1], row[2], row[3], row[4], row[5], row[6]]
            history_tree.insert("", "end", values=data_in_order)

        conn.close()
    except sqlite3.Error as e:
        messagebox.showerror("Error",
                             f"An error occurred while fetching data from the 'Historique' table: {str(e)}")


def update_label_periodically():
    window.after(1000, watch_get_key_file)

    # window.after(2000, update_history_table)  # Update every 1 seconds


def update_time_remaining_label():
    heur_rappel = calculate_time_remaining()
    if heur_rappel.days == 0 and heur_rappel.seconds == 0:
        next_month_day = calculate_next_month_day()
        query_thread()
        time_until_next_month_day = next_month_day - datetime.datetime.now()
        days = time_until_next_month_day.days
        hours = time_until_next_month_day.seconds // 3600
        minutes = (time_until_next_month_day.seconds // 60) % 60
        seconds = time_until_next_month_day.seconds % 60
        time_remaining_label["text"] = "Prochain compte à rebours avant le prochain get_keyoi : " + \
                                       format_time(days, hours, minutes, seconds)
    else:
        days = heur_rappel.days
        hours = heur_rappel.seconds // 3600
        minutes = (heur_rappel.seconds // 60) % 60
        seconds = heur_rappel.seconds % 60
        time_remaining_label["text"] = "Temps restant jusqu'au prochain get_keyoi : " + \
                                       format_time(days, hours, minutes, seconds)


def query_thread():
    query = threading.Thread(target=execute_script, args=())
    query.start()


# Function to update the configuration values in the database
def update_config_in_database(key, value):
    with sqlite3.connect(database_path) as conn:
        cursor = conn.cursor()

        # Update the corresponding rows in the 'Configuration' table
        cursor.execute("UPDATE Configuration SET value=? WHERE key=?", (value, key))

        conn.commit()

        # Update the current smtp dictionary if necessary
        if key in smtp:
            smtp[key] = value


def update_config():
    config_widgets = []
    # Create the popup window
    # Calculate the total height required based on the number of widgets
    config_popup = tk.Toplevel(window)
    config_popup.title("Modifier les configurations")
    config_popup.resizable(False, False)

    # Create a frame for all the configuration widgets
    config_frame = ttk.Frame(config_popup, padding=20)
    config_frame.pack(fill=tk.BOTH, expand=True)

    # Create labels and entry fields to display and modify the config data
    objet_email_label = ttk.Label(config_frame, text="Objet du mail:")
    objet_email_entry = ttk.Entry(config_frame)
    objet_email_entry.insert(tk.END, get_key('OBJET'.lower()))

    message_email_label = ttk.Label(config_frame, text="Message Email:")
    message_email_entry = ttk.Entry(config_frame)
    message_email_entry.insert(tk.END, get_key('MESSAGE'.lower()))

    server_label = ttk.Label(config_frame, text="SMTP Serveur:")
    server_entry = ttk.Entry(config_frame)
    server_entry.insert(tk.END, get_key('SMTP_SERVEUR'.lower()))

    username_label = ttk.Label(config_frame, text="SMTP Username:")
    username_entry = ttk.Entry(config_frame)
    username_entry.insert(tk.END, get_key('SMTP_USERNAME'.lower()))

    password_label = ttk.Label(config_frame, text="SMTP Password:")
    password_entry = ttk.Entry(config_frame, show="*")
    password_entry.insert(tk.END, get_key('SMTP_PASSWORD'.lower()))

    port_label = ttk.Label(config_frame, text="SMTP Port:")
    port_entry = ttk.Entry(config_frame)
    port_entry.insert(tk.END, get_key('SMTP_PORT'.lower()))

    # Entry fields for [SETTINGS] section
    set_hour_label = ttk.Label(config_frame, text="Heure:")
    set_hour_entry = ttk.Entry(config_frame)
    set_hour_entry.insert(tk.END, get_key('SET_HOUR'.lower()))

    set_minute_label = ttk.Label(config_frame, text="Minute:")
    set_minute_entry = ttk.Entry(config_frame)
    set_minute_entry.insert(tk.END, get_key('SET_MINUTE'.lower()))

    set_second_label = ttk.Label(config_frame, text="Seconde:")
    set_second_entry = ttk.Entry(config_frame)
    set_second_entry.insert(tk.END, get_key('SET_SECOND'.lower()))

    set_microsecond_label = ttk.Label(config_frame, text="Microseconde:")
    set_microsecond_entry = ttk.Entry(config_frame)
    set_microsecond_entry.insert(tk.END, get_key('SET_MICROSECOND'.lower()))

    set_day_label = ttk.Label(config_frame, text="Jour:")
    set_day_entry = ttk.Entry(config_frame)
    set_day_entry.insert(tk.END, get_key('SET_DAY'.lower()))

    # Entry fields for [LOCAL] section
    database_name_label = ttk.Label(config_frame, text="Nom de la base de données:")
    database_name_entry = ttk.Entry(config_frame)
    database_name_entry.insert(tk.END, get_key('DATABASE_NAME'.lower()))

    def validate_int_input(input_str):
        try:
            int(input_str)
            return True
        except ValueError:
            return False

    def validate_config_values():
        # Validate the integer values in the [SETTINGS] section
        if not validate_int_input(set_hour_entry.get()):
            messagebox.showerror("Error", "Heure doit être un entier.")
            return False

        if not validate_int_input(set_minute_entry.get()):
            messagebox.showerror("Error", "Minute doit être un entier.")
            return False

        if not validate_int_input(set_second_entry.get()):
            messagebox.showerror("Error", "Seconde doit être un entier.")
            return False

        if not validate_int_input(set_microsecond_entry.get()):
            messagebox.showerror("Error", "Microseconde doit être un entier.")
            return False

        if not validate_int_input(set_day_entry.get()):
            messagebox.showerror("Error", "Jour doit être un entier.")
            return False

        return True

    # Function to save the modified data to the .get_key file
    def save_config():
        try:
            # Validate the input values before saving
            if not validate_config_values():
                return

            # Update the configurations in the database
            update_config_in_database('objet', objet_email_entry.get())
            update_config_in_database('message', message_email_entry.get())
            update_config_in_database('smtp_serveur', server_entry.get())
            update_config_in_database('smtp_username', username_entry.get())
            update_config_in_database('smtp_password', password_entry.get())
            update_config_in_database('smtp_port', port_entry.get())
            update_config_in_database('set_hour', set_hour_entry.get())
            update_config_in_database('set_minute', set_minute_entry.get())
            update_config_in_database('set_second', set_second_entry.get())
            update_config_in_database('set_microsecond', set_microsecond_entry.get())
            update_config_in_database('set_day', set_day_entry.get())
            update_config_in_database('database_name', database_name_entry.get())

            messagebox.showinfo("Success", "Configurations saved successfully.")

            # Close the configuration popup window
            config_popup.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving configurations: {str(e)}")

            # Close the configuration popup window
            config_popup.destroy()

    # Create a save button to save the changes
    save_button = ttk.Button(config_frame, text="Enregistrer", command=save_config)

    # Grid layout for the popup widgets

    server_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
    server_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

    username_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
    username_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

    password_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
    password_entry.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

    port_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
    port_entry.grid(row=3, column=1, padx=10, pady=5, sticky="ew")

    # Grid layout for the [SETTINGS] section
    set_hour_label.grid(row=4, column=0, padx=10, pady=5, sticky="w")
    set_hour_entry.grid(row=4, column=1, padx=10, pady=5, sticky="ew")

    set_minute_label.grid(row=5, column=0, padx=10, pady=5, sticky="w")
    set_minute_entry.grid(row=5, column=1, padx=10, pady=5, sticky="ew")

    set_second_label.grid(row=6, column=0, padx=10, pady=5, sticky="w")
    set_second_entry.grid(row=6, column=1, padx=10, pady=5, sticky="ew")

    set_microsecond_label.grid(row=7, column=0, padx=10, pady=5, sticky="w")
    set_microsecond_entry.grid(row=7, column=1, padx=10, pady=5, sticky="ew")

    set_day_label.grid(row=8, column=0, padx=10, pady=5, sticky="w")
    set_day_entry.grid(row=8, column=1, padx=10, pady=5, sticky="ew")

    # Grid layout for the [LOCAL] section
    database_name_label.grid(row=10, column=0, padx=10, pady=5, sticky="w")
    database_name_entry.grid(row=10, column=1, padx=10, pady=5, sticky="ew")

    objet_email_label.grid(row=11, column=0, padx=10, pady=5, sticky="w")
    objet_email_entry.grid(row=11, column=1, padx=10, pady=5, sticky="ew")

    message_email_label.grid(row=12, column=0, padx=10, pady=5, sticky="w")
    message_email_entry.grid(row=12, column=1, padx=10, pady=5, sticky="ew")

    save_button.grid(row=13, column=0, columnspan=2, pady=10)

    # Append each widget to the config_widgets list
    config_widgets.extend([
        server_label, server_entry, username_label, username_entry, password_label, password_entry,
        port_label, port_entry, set_hour_label, set_hour_entry, set_minute_label, set_minute_entry,
        set_second_label, set_second_entry, set_microsecond_label, set_microsecond_entry,
        set_day_label, set_day_entry, database_name_label, database_name_entry,
        objet_email_label, objet_email_entry, message_email_label, message_email_entry, save_button
    ])

    # Calculate the total height required based on the number of widgets
    total_height = sum(widget.winfo_reqheight() for widget in config_widgets) + 30  # Add some extra padding

    # Update the geometry of the popup window to adjust its height
    config_popup.geometry(f"400x{total_height}")


if __name__ == "__main__":
    window = tk.Tk()
    window.title("Programme d'get_keyoi de données")
    window.geometry("800x500")  # Set a default window size

    # Set a custom style for widgets
    style = ttk.Style()
    style.configure('Custom.TLabel', font=('Helvetica', 20), padding=10)
    style.configure('Custom.TButton', font=('Helvetica', 16), padding=10)
    style.configure('Custom.Treeview', font=('Helvetica', 12))
    style.configure('Custom.Treeview.Heading', font=('Helvetica', 14, 'bold'), background='#dcdcdc', foreground='black')
    style.configure('Custom.Treeview', background='#f0f0f0')  # Set Treeview background color

    # Define the layout for the 'Custom.TLabel.Colored' style
    style.layout('Custom.TLabel.Colored',
                 [('Label.border', {'sticky': 'nswe', 'children':
                     [('Label.padding', {'sticky': 'nswe', 'children':
                         [('Label.label', {'sticky': 'nswe'})],
                                         'border': '2'})],
                                    'border': '2'})])

    # Create a frame for the header
    header_frame = ttk.Frame(window)
    header_frame.pack(fill=tk.X, pady=10)

    # Load your company logo and add it to the header
    logo_img = Image.open("logo-inviso.ico")  # Replace "path_to_your_logo.png" with the path to your logo
    logo_img = logo_img.resize((70, 70), Image.LANCZOS)  # Resize the logo as needed
    logo_img = ImageTk.PhotoImage(logo_img)

    logo_label = ttk.Label(header_frame, image=logo_img)
    logo_label.pack(side=tk.LEFT, padx=10)

    # Create a frame to hold the "Execute" and "Config" buttons
    buttons_frame = ttk.Frame(header_frame)
    buttons_frame.pack(side=tk.RIGHT, padx=10)

    # Load the icons for buttons
    execute_icon_img = Image.open("execute_icon.png")  # Replace with the path to your execute icon
    execute_icon_img = execute_icon_img.resize((30, 30), Image.LANCZOS)  # Use Image.LANCZOS instead of Image.ANTIALIAS
    execute_icon = ImageTk.PhotoImage(execute_icon_img)

    config_icon_img = Image.open("config_icon.png")  # Replace with the path to your config icon
    config_icon_img = config_icon_img.resize((30, 30), Image.LANCZOS)  # Use Image.LANCZOS instead of Image.ANTIALIAS
    config_icon = ImageTk.PhotoImage(config_icon_img)

    # Bouton pour exécuter le script
    execute_button = ttk.Button(buttons_frame, command=query_thread, image=execute_icon, style='Custom.TButton')
    execute_button.pack(side=tk.LEFT, padx=5, pady=5)

    # Create a "Config" button to modify the configurations
    config_button = ttk.Button(buttons_frame, command=update_config, image=config_icon, style='Custom.TButton')
    config_button.pack(side=tk.LEFT, padx=5, pady=5)

    # Create the colored label using the 'Custom.TLabel.Colored' style for the timer section
    time_remaining_label = ttk.Label(window, text="get_keyoi de Mail Automatique", font=('Helvetica', 20),
                                     style='Custom.TLabel.Colored')
    time_remaining_label.pack(pady=10)

    # Create a Treeview widget to display the history table
    history_tree = ttk.Treeview(window, columns=("Date", "Heure", "Objet", "Email", "Message", "Donnée", "Statut"),
                                show="headings", style='Custom.Treeview')
    history_tree.heading("Date", text="Date", anchor=tk.CENTER)
    history_tree.heading("Heure", text="Heure", anchor=tk.CENTER)
    history_tree.heading("Objet", text="Objet", anchor=tk.CENTER)
    history_tree.heading("Email", text="Email", anchor=tk.CENTER)
    history_tree.heading("Message", text="Message", anchor=tk.CENTER)
    history_tree.heading("Donnée", text="Donnée", anchor=tk.CENTER)
    history_tree.heading("Statut", text="Statut", anchor=tk.CENTER)

    # Add a vertical scrollbar to the right of the table
    scrollbar = ttk.Scrollbar(window, orient="vertical", command=history_tree.yview)
    history_tree.configure(yscrollcommand=scrollbar.set)

    history_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)  # Use pack for the scrollbar

    # Set a custom background color for the window
    window.configure(bg='#ffffff')

    # Call the function to update the label and history table periodically
    update_label_periodically()

    # Start the tkinter main loop
    window.mainloop()
