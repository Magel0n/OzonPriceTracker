# Ozon Goods Price Tracker

This is a python project for a web application that
tracks prices of goods on Ozon and sends notifications
via telegram to the user when that good falls below a
certain price threshold.

To run the project locally, first, install dependencies
using poetry:

```batch
poetry install
```

Then, in separate terminal windows, run these two commands

```batch
poetry run python app\api.py
poetry run streamlit run app\app.py
```
