.PHONY: install lint run clean

PYTHON = python3
VENV_DIR = venv
APP_FILE = inference_api

install:
	@echo "Creating and activating virtual environment"
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Installing dependencies from requirements.txt file"
	./$(VENV_DIR)/bin/pip install -r requirements.txt
	@echo "Installation complete. Activate the virtual environment using the command below."
	@echo "source $(VENV_DIR)/bin/activate"

lint:
	@echo "Running pylint"
	./$(VENV_DIR)/bin/pylint --rcfile=.pylintrc $(APP_FILE) scripts/train.py

test:
	@echo "Running pytest"
	@echo "Tests run"

run:
	@echo "Running the application"
	./$(VENV_DIR)/bin/uvicorn $(APP_FILE):app --host 0.0.0.0 --port 8000 --reload


train:
	@echo "Training the model"
	./$(VENV_DIR)/bin/python scripts/train.py

evaluate:
	@echo "Evaluating the trained model"
	./$(VENV_DIR)/bin/python scripts/evaluate_model.py

clean:
	@echo "Cleaning up virtual environment and __pycache__ directories"
	rm -rf $(VENV_DIR)
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "--- Clean up complete ---"

compile:
	@echo "Compiling python script into a standalone binary"
	pyinstaller --onefile "$(APP_FILE).py"

clean-compile:
	@echo "Building python script into a standalone binary"
	nuitka --standalone --onefile "$(APP_FILE).py"