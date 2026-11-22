import logging
import re
import sys

import opensilexClientToolsPython as silex
import pandas as pd
from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from simple.auth import (
    INSTANCES,
    SANDBOX_URL,
    check_connection_internet,
    connect,
    is_connected,
)
from simple.data_import import (
    create_factor,
    create_germplasm,
    create_sci_obj,
)
from simple.datafile_import import check_for_datafiles
from simple.errors import (
    AuthenticationError,
    NetworkError,
)
from simple.experiment import api_find_experiment_by_name, create_experiment
from simple.import_service import (
    plan_datafiles_import,
    run_datafiles_import,
    run_tabular_import,
    upload_datafiles,
)
from simple.logging_setup import logger


# 1. The Signal Emitter (Safely crosses threads)
class LogEmitter(QObject):
    log_signal = pyqtSignal(str, str)

class WorkerThread(QThread):
    # These signals safely carry our results back to the main GUI thread
    finished_success = pyqtSignal(object) 
    finished_error = pyqtSignal(Exception)

    def __init__(self, task_func):
        super().__init__()
        self.task_func = task_func

    def run(self):
        try:
            # Execute the heavy backend function
            result = self.task_func()
            self.finished_success.emit(result)
        except Exception as e:
            # Intentional broad catch at the worker-thread boundary: any
            # backend failure must reach the GUI thread as a signal, otherwise
            # the worker dies silently and the progress dialog never closes.
            self.finished_error.emit(e)

# 2. The Custom Logging Handler
class GUIConsoleHandler(logging.Handler):
    def __init__(self, emitter):
        super().__init__()
        self.emitter = emitter
        self.setLevel(logging.INFO) # <-- Back to INFO!

    def emit(self, record):
        msg = self.format(record)
        
        # Strip out the CLI-specific rich tags (like [green], [/bold cyan]) but keep [✓]
        clean_msg = re.sub(r'\[/?(?:bold\s)?(?:green|red|cyan|yellow|blue|magenta|white)\]', '', msg)
        
        if record.levelno == logging.WARNING:
            color = "#f29d00" 
        elif record.levelno >= logging.ERROR:
            color = "#ab2d2d" 
        else:
            color = "#195819" 

        html_msg = f'<span style="color: {color};">{clean_msg}</span>'
        
        # Send both the HTML for display and the clean text for our deduplicator
        self.emitter.log_signal.emit(html_msg, clean_msg.strip())

class SimpleGUI(QMainWindow):

    gui_progress_signal = pyqtSignal(str, int, int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIMPLE GUI")
        self.setMinimumSize(500, 500)

        # INITIALISATION DES VARIABLES et de l'api ~
        self.api_client = silex.ApiClient(verbose=False)
        self.login_info = None
        self.experiment_directory = None
        self.miappe_path = None
        self.data_path = None
        self.photos_directory = None

        self.init_ui()
        self.gui_progress_signal.connect(self._safe_update_progress)
        self.current_progress = 0

    def _safe_append_console(self, html_msg, clean_msg):
        # If the incoming text matches the last printed text, ignore it.
        self.console_output.moveCursor(QTextCursor.MoveOperation.End)
        if clean_msg == self.last_console_msg:
            return 
            
        self.last_console_msg = clean_msg
        self.console_output.appendHtml(html_msg)

    def _safe_update_progress(self, label_text, advance=0, total=0):
        """This function always runs on the main thread and safely updates the UI."""
        if not hasattr(self, 'progress') or self.progress.wasCanceled():
            return

        clean_label = re.sub(r'\[/?(?:bold\s)?(?:green|red|cyan|yellow|blue|magenta|white)\]', '', label_text)
        # Only reset the progress and update the maximum if a NEW total is provided.
        # This prevents the bar from resetting to 0 if the backend repeatedly sends the same total.
        if total > 0 and (self.progress.maximum() != total or self.current_progress >= self.progress.maximum()):
            self.progress.setMaximum(total)
            self.current_progress = 0 # Reset only when the total changes
            
        self.current_progress += advance
        self.progress.setValue(self.current_progress)
        
        # 3. Apply the clean label to the UI
        self.progress.setLabelText(f"{clean_label}...")

    def closeEvent(self, event):
        # Clean up the logger handler when the app closes
        logger.removeHandler(self.gui_logger_handler)
        super().closeEvent(event)
        

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.status_label = QLabel("Not logged in.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.btn_login = QPushButton("1. Log In")
        self.btn_login.clicked.connect(self.action_login)
        layout.addWidget(self.btn_login)

        self.btn_find_exp = QPushButton("2. Find Experiment")
        self.btn_find_exp.clicked.connect(self.action_find_experiment)
        layout.addWidget(self.btn_find_exp)

        self.btn_import_menu = QPushButton("3. Import Data")
        self.btn_import_menu.clicked.connect(self.action_open_import_menu)
        layout.addWidget(self.btn_import_menu)

        self.btn_reset = QPushButton("4. Reset Working Directory")
        self.btn_reset.clicked.connect(self.action_reset)
        layout.addWidget(self.btn_reset)

        self.btn_quit = QPushButton("Quit")
        self.btn_quit.clicked.connect(self.close)
        layout.addWidget(self.btn_quit)

        # --- NEW CONSOLE WIDGET ---
        layout.addWidget(QLabel("Console Output:"))
        from PyQt6.QtWidgets import QPlainTextEdit
        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        # Optional: set a darker background to make it look like a terminal
        self.console_output.setStyleSheet(
            "background-color: #d4d4d4; "
            "color: #d4d4d4; "
            "font-family: monospace; "
            "font-size: 13px; "
            "font-weight: bold;"
        )
        layout.addWidget(self.console_output)

        # --- WIRE THE LOGGER TO THE CONSOLE ---
        self.log_emitter = LogEmitter()
        self.last_console_msg = "" # <-- ADD THIS to remember the last message
        self.log_emitter.log_signal.connect(self._safe_append_console)

        self.gui_logger_handler = GUIConsoleHandler(self.log_emitter)
        self.gui_logger_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        
        # Attach our custom handler to the engine's logger
        logger.addHandler(self.gui_logger_handler)


    def action_login(self):
        custom_label = "Custom URL..."
        host_display, ok = QInputDialog.getItem(
            self,
            "Login",
            "Select host instance:",
            list(INSTANCES.values()) + [custom_label],
            0,
            False,
        )
        if not ok:
            return

        if host_display == custom_label:
            host, ok = QInputDialog.getText(self, "Login", "Instance REST URL:")
            if not ok or not host.strip():
                return
            host = host.strip()
        else:
            host = next(key for key, value in INSTANCES.items() if value == host_display)

        if host == SANDBOX_URL:
            identifier="guest@opensilex.org"
            password="guest"
            self.login_info = {"host": host, "identifier": identifier, "password": password}
        else:
            identifier, ok = QInputDialog.getText(self, "Login", "Identifier:")
            if not ok:
                return
            password, ok = QInputDialog.getText(
                self, "Login", "Password:", QLineEdit.EchoMode.Password
            )
            if not ok:
                return

            self.login_info = {"host": host, "identifier": identifier, "password": password}

        try:
            connect(self.login_info, self.api_client)
            self.status_label.setText(
                f"Logged in as {identifier} on {INSTANCES.get(host, host)}"
            )
            QMessageBox.information(self, "Success", "Connected successfully.")
        except AuthenticationError as e:
            QMessageBox.critical(self, "Auth Error", str(e))

    def action_find_experiment(self):
        if not is_connected(self.api_client):
            QMessageBox.warning(self, "Error", "Please log in first.")
            return

        name_exp, ok = QInputDialog.getText(self, "Find Experiment", "Experiment name:")
        if ok and name_exp:
            self.with_progress(
                "Searching...",
                lambda: api_find_experiment_by_name(self.api_client, name_exp),
                self._display_experiment,
            )

    def _display_experiment(self, exp_data):
        if not exp_data:
            QMessageBox.information(self, "Result", "No experiment found.")
            return
        exp = exp_data[0]
        details = f"URI: {exp.uri}\n\nName: {exp.name}\n\nDescription: {exp.description}\n\nObjectives: {exp.objective}"
        QMessageBox.information(self, "Experiment Info", details)

    def action_open_import_menu(self):
        if not is_connected(self.api_client):
            QMessageBox.warning(self, "Error", "Please log in first.")
            return

        if not self.experiment_directory:
            self.experiment_directory = QFileDialog.getExistingDirectory(
                self, "Select Working Directory"
            )
            if not self.experiment_directory:
                return

            self.miappe_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select MIAPPE file",
                self.experiment_directory,
                "Excel Files (*.xlsx *.xls)",
            )
            self.data_path, _ = QFileDialog.getOpenFileName(
                self, "Select Data file", self.experiment_directory, "Excel Files (*.xlsx xls)"
            )

        self.import_dialog = QDialog(self)
        self.import_dialog.setWindowTitle("Experiment Menu")
        layout = QVBoxLayout(self.import_dialog)

        buttons = [
            ("1. Create Experiment", self.do_create_experiment),
            ("2. Import Germplasm", self.do_import_germplasm),
            ("3. Import Factor", self.do_import_factor),
            ("4. Import Scientific Objects", self.do_import_sci_obj),
            ("5. Import Datafiles", self.do_import_datafiles),
            ("6. Import Tabular Data", self.do_import_data),
            ("7. Run All Imports", self.do_run_all),
        ]

        for text, func in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            layout.addWidget(btn)

        self.import_dialog.exec()

    def action_reset(self):
        self.experiment_directory = None
        self.miappe_path = None
        self.data_path = None
        self.photos_directory = None
        QMessageBox.information(
            self, "Reset", "Working directory and selected files have been reset."
        )
    
    def with_progress(self, message, task_func, on_success_callback=None, indeterminate=False):
        # 1. Setup the beautiful, non-freezing Progress Dialog
        self.progress = QProgressDialog(message, None, 0, 100, self) 
        self.progress.setWindowTitle("Please wait")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress.setAutoClose(False) 
        
        # Explicitly reset the internal progress tracker for each new task
        self.current_progress = 0 
        
        if indeterminate:
            # Setting max and min to 0 triggers the infinite loading animation
            self.progress.setMaximum(0)
            self.progress.setMinimum(0)
        else:
            self.progress.setValue(0)
            
        self.progress.show()

        # 2. Create the background worker
        self.worker = WorkerThread(task_func)

        # 3. Connect the success signal
        if on_success_callback:
            # When the worker finishes successfully, close the bar and run the callback
            self.worker.finished_success.connect(self.progress.close)
            self.worker.finished_success.connect(on_success_callback)

        # 4. Connect the error signal (Crucial: prevents silent crashes!)
        def handle_error(e):
            self.progress.close()
            logger.error(f"Task Failed: {e!s}")
            QMessageBox.critical(self, "Error", f"An error occurred during import:\n{e!s}")
            
        self.worker.finished_error.connect(handle_error)

        # 5. Start the thread! The GUI remains 100% responsive.
        self.worker.start()

    def _status_callback(self, message):
        import re
        # Clean the tags here as well
        clean_msg = re.sub(r'\[/?(?:bold\s)?(?:green|red|cyan|yellow|blue|magenta|white)\]', '', message)
        
        html_msg = f'<span style="color: #008000;">{clean_msg}</span>'
        self.log_emitter.log_signal.emit(html_msg, clean_msg.strip())

    def do_create_experiment(self):
        def task():
            return create_experiment(
                self.miappe_path,
                self.api_client,
                status_callback=self._status_callback,
            )

        def finish(results):
            # affichage final
            msg = "\n".join([f"experiment {name} created or found with uri: {uri}" for name, uri in results.items()])
            QMessageBox.information(self, "Experiment creater or found", msg)

        self.with_progress(
            "Creating/fetching experiment...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Experiment imported/found."),
            indeterminate=True
        )

    def do_import_germplasm(self):
        def task():
            return create_germplasm(self.miappe_path, self.api_client)

        self.with_progress(
            "Creating/fetching germplasms...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Germplasms imported/found."),
            indeterminate=True
        )

    def do_import_factor(self):
        def task():
            return create_factor(self.miappe_path, self.api_client)

        self.with_progress(
            "Creating/fetching factors...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Factors imported/found."),
            indeterminate=True 
        )

    def do_import_sci_obj(self):
        def task():
            return create_sci_obj(
                self.data_path,
                self.miappe_path,
                self.api_client,
                status_callback=self._status_callback,
            )

        def finish(res):
            sci_obj_uri, created_sci_obj = res
            found = len(sci_obj_uri) - created_sci_obj
            QMessageBox.information(
                self, "Scientific Objects", f"{found} scientific objects found and {created_sci_obj} created."
            )
        self.with_progress(
            "Creating/fetching Scientific objects...",
            task,
            finish,
            indeterminate=True,
        )

    def do_import_datafiles(self):
        self.photos_directory = QFileDialog.getExistingDirectory(self, "Select Photo Directory", self.experiment_directory)
        if not self.photos_directory:
            return

        # 1. UI interaction must happen in the main thread before starting the background task
        datafile_check = check_for_datafiles(self.data_path, self.photos_directory)
        _, missing_datafile1, _, missing_datafile2, _, _ = datafile_check

        if missing_datafile1 or missing_datafile2:
            logger.warning(f"{missing_datafile1} & {missing_datafile2}")
            reply = QMessageBox.question(
                self,
                "Discrepancies found",
                "Datafiles are missing. Continue despite discrepancies? The import may fail.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        def task():
            def confirm_protocol(protocol_found):
                if not protocol_found:
                    logger.warning("PlantMask and Camera Position were not found")
                return True

            def update_progress_bar(task_name, total=None, advance=0):
                safe_total = total if total is not None else 0
                self.gui_progress_signal.emit(task_name, advance, safe_total)

            run_datafiles_import(
                self.miappe_path,
                self.data_path,
                self.experiment_directory,
                self.login_info,
                self.api_client,
                self.photos_directory,
                confirm_create_default_provenances=lambda missing: True,
                confirm_protocol=confirm_protocol,
                confirm_discrepancies=lambda missing1, missing2: True,
                confirm_upload=lambda: True,
                datafile_check=datafile_check,
                status_callback=lambda mess: logger.info(mess),
                progress_callback=update_progress_bar,
            )

        # 3. Use a lambda for the missing success_callback
        self.with_progress(
            "Importing datafiles...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Datafiles imported successfully.")
        )

    def do_import_data(self):
        def task():
            total_operations = {"value": 0}

            def confirm_data_mapping(morpho_info):
                # Calculate the total upfront (number of variables * rows)
                total_operations["value"] = len(morpho_info) * len(
                    pd.read_excel(self.data_path)
                )
                return True

            def show_progress(variable_name, line_count):
                # Pass the calculated total so the UI knows how to scale
                self.gui_progress_signal.emit(
                    f"Adding to {variable_name}",
                    line_count,
                    total_operations["value"],
                )

            run_tabular_import(
                self.data_path,
                self.miappe_path,
                self.login_info,
                self.api_client,
                confirm_data_mapping=confirm_data_mapping,
                confirm_create_default_provenances=lambda missing: True,
                progress_callback=show_progress,
            )

        # 3. Use a lambda for the missing success_callback
        self.with_progress(
            "Importing tabular data...",
            task,
            lambda r: QMessageBox.information(self, "Success", "Tabular data imported successfully.")
        )

    def do_run_all(self):
        # 1. Handle all UI Pop-ups in the main thread first
        self.photos_directory = QFileDialog.getExistingDirectory(self, "Select Photo Directory", self.experiment_directory)
        if not self.photos_directory:
            return

        # Check for missing datafiles before locking up the UI
        datafile_check = check_for_datafiles(self.data_path, self.photos_directory)
        _, missing_datafile1, _, missing_datafile2, _, _ = datafile_check

        if missing_datafile1 or missing_datafile2:
            reply = QMessageBox.question(
                self,
                "Discrepancies found",
                "Datafiles are missing. Continue despite discrepancies?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # 2. Create ONE master background task that runs everything sequentially
        def master_task():
            # --- 1. Experiment ---
            self.gui_progress_signal.emit("Creating experiment", 0, 0)
            create_experiment(self.miappe_path, self.api_client, status_callback=self._status_callback)

            # --- 2. Germplasm ---
            self.gui_progress_signal.emit("Importing germplasms", 0, 0)
            create_germplasm(self.miappe_path, self.api_client)

            # --- 3. Factors ---
            self.gui_progress_signal.emit("Importing factors", 0, 0)
            create_factor(self.miappe_path, self.api_client)

            # --- 4. Scientific Objects ---
            sci_obj_uri, created_sci_obj = create_sci_obj(
                self.data_path, self.miappe_path, self.api_client,
                status_callback=self._status_callback
            )

            # --- 5. Datafiles ---
            self.gui_progress_signal.emit("Checking provenances", 0, 0)

            def update_datafile_progress_bar(task_name, total=None, advance=0):
                safe_total = total if total is not None else 0
                self.gui_progress_signal.emit(task_name, advance, safe_total)

            plan = plan_datafiles_import(
                self.miappe_path,
                self.data_path,
                self.experiment_directory,
                self.api_client,
                self.photos_directory,
                confirm_create_default_provenances=lambda missing: True,
                confirm_protocol=lambda protocol_found: True,
                confirm_discrepancies=lambda missing1, missing2: True,
                confirm_upload=lambda: True,
                datafile_check=datafile_check,
                sci_obj=(sci_obj_uri, created_sci_obj),
            )
            upload_datafiles(
                plan,
                self.miappe_path,
                self.data_path,
                self.login_info,
                self.api_client,
                status_callback=self._status_callback,
                progress_callback=update_datafile_progress_bar,
            )

            # --- 6. Tabular Data ---
            total_operations = {"value": 0}

            def confirm_data_mapping(morpho_info):
                total_operations["value"] = len(morpho_info) * len(
                    pd.read_excel(self.data_path)
                )
                return True

            def show_progress(variable_name, line_count):
                self.gui_progress_signal.emit(
                    f"Adding to {variable_name}",
                    line_count,
                    total_operations["value"],
                )

            run_tabular_import(
                self.data_path,
                self.miappe_path,
                self.login_info,
                self.api_client,
                confirm_data_mapping=confirm_data_mapping,
                confirm_create_default_provenances=lambda missing: True,
                progress_callback=show_progress,
                provenances=(plan.prov_dict, plan.datafile_provenance),
                sci_obj=(sci_obj_uri, created_sci_obj),
            )

        # 3. Fire up the single thread using the indeterminate loader we built earlier
        self.with_progress(
            "Starting batch import...",
            master_task,
            lambda r: QMessageBox.information(self, "Success", "All imports finished successfully!"),
            indeterminate=True
        )


def main():
    try:
        check_connection_internet()
    except NetworkError as e:
        logger.error(f"Network Error: {e}")
        return

    app = QApplication(sys.argv)
    window = SimpleGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
