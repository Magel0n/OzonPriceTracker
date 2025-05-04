import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os
from typing import Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
STATIC_FILES_URL = os.getenv("STATIC_FILES_URL", "http://localhost:8000/static")


def make_api_request(endpoint: str, method: str = "GET", data: Optional[dict] = None):
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data)
        elif method.upper() == "DELETE":
            response = requests.delete(url, json=data)
        else:
            return None, "Invalid HTTP method"

        if response.status_code == 200:
            return response.json(), None
        else:
            error_data = response.json()
            return None, error_data.get("message", "Unknown error occurred")
    except requests.exceptions.RequestException as e:
        return None, f"Connection error: {str(e)}"


def display_user_info(user_tid: str):
    """Display user information and tracked products."""
    data, error = make_api_request(f"/user/{user_tid}")

    if error:
        st.error(f"Failed to load user data: {error}")
        return

    user = data["user"]
    tracked_products = data["tracked_products"]

    # User profile section
    col1, col2 = st.columns([1, 3])
    with col1:
        if user["user_pfp"]:
            st.image(f"{STATIC_FILES_URL}/profile-pictures/{user['tid']}", width=100)
        else:
            st.image("https://via.placeholder.com/100", width=100)

    with col2:
        st.subheader(user["name"])
        st.caption(f"@{user['username']}")

    # Tracked products section
    st.subheader("Tracked Products")
    if not tracked_products:
        st.info("You are not tracking any products yet.")
    else:
        for product in tracked_products:
            with st.expander(f"{product['name']} - {product['price']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Seller:** {product['seller']}")
                    st.markdown(f"**URL:** [{product['url']}]({product['url']})")
                    st.markdown(f"**Tracking price:** {product['tracking_price']}")

                with col2:
                    # Price threshold update form
                    with st.form(key=f"threshold_form_{product['product_id']}"):
                        new_threshold = st.text_input(
                            "Price threshold",
                            value=product["tracking_price"],
                            key=f"threshold_{product['product_id']}"
                        )
                        submitted = st.form_submit_button("Update threshold")
                        if submitted:
                            update_data = {
                                "user_tid": user_tid,
                                "product_id": product["product_id"],
                                "new_price": new_threshold
                            }
                            _, error = make_api_request("/tracking", "PUT", update_data)
                            if error:
                                st.error(f"Failed to update threshold: {error}")
                            else:
                                st.success("Threshold updated successfully!")
                                st.rerun()

                    # Delete tracking button
                    if st.button("Stop tracking", key=f"delete_{product['product_id']}"):
                        delete_data = {
                            "user_tid": user_tid,
                            "product_id": product["product_id"]
                        }
                        _, error = make_api_request("/tracking", "DELETE", delete_data)
                        if error:
                            st.error(f"Failed to stop tracking: {error}")
                        else:
                            st.success("Product removed from tracking list")
                            st.rerun()

                # Price history chart
                st.subheader("Price History")
                history_data, error = make_api_request(f"/product/{product['product_id']}/history")
                if error:
                    st.warning(f"Could not load price history: {error}")
                else:
                    history = history_data["history"]
                    if history:
                        df = pd.DataFrame(history, columns=["timestamp", "price"])
                        df["price"] = df["price"].astype(float)
                        df["date"] = pd.to_datetime(df["timestamp"], unit="s")

                        fig = px.line(
                            df,
                            x="date",
                            y="price",
                            title="Price History",
                            labels={"price": "Price", "date": "Date"}
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No price history available for this product.")


def add_product_form(user_tid: str):
    """Form to add a new product to track."""
    with st.form(key="add_product_form"):
        st.subheader("Add New Product to Track")

        method = st.radio(
            "Add by:",
            ("Product URL", "SKU"),
            horizontal=True
        )

        if method == "Product URL":
            product_url = st.text_input("Product URL")
            product_sku = None
        else:
            product_sku = st.text_input("Product SKU")
            product_url = None

        price_threshold = st.text_input("Notify me when price drops below")

        submitted = st.form_submit_button("Start Tracking")
        if submitted:
            if not (product_url or product_sku):
                st.error("Please provide either a URL or SKU")
                return

            if not price_threshold:
                st.error("Please set a price threshold")
                return

            tracking_data = {
                "user_tid": user_tid,
                "product_url": product_url,
                "product_sku": product_sku
            }

            response, error = make_api_request("/tracking", "POST", tracking_data)
            if error:
                st.error(f"Failed to add product: {error}")
            else:
                # Now update the threshold
                update_data = {
                    "user_tid": user_tid,
                    "product_id": response["product_id"],
                    "new_price": price_threshold
                }
                _, error = make_api_request("/tracking", "PUT", update_data)
                if error:
                    st.error(f"Product added but failed to set threshold: {error}")
                else:
                    st.success("Product added to tracking list!")
                    st.rerun()


def product_search(user_tid: str):
    """Search and filter products."""
    st.subheader("Product Search")

    search_query = st.text_input("Search by product name or seller")
    min_price = st.number_input("Minimum price", min_value=0.0, value=0.0)
    max_price = st.number_input("Maximum price", min_value=0.0, value=1000.0)

    if st.button("Search"):
        # just show a message
        st.info("Search functionality would be implemented here with a proper backend endpoint")


def login_page():
    st.title("Product Price Tracker")

    # For demo purposes, use a simple user ID input
    user_tid = st.text_input("Enter your Telegram User ID")

    if st.button("Login"):
        if user_tid:
            # For now, just store the user ID in session state
            st.session_state["user_tid"] = user_tid
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Please enter your Telegram User ID")


def main():
    st.set_page_config(page_title="Product Tracker", layout="wide")

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        login_page()
    else:
        user_tid = st.session_state["user_tid"]

        st.sidebar.title("Menu")
        page = st.sidebar.radio(
            "Navigation",
            ["My Products", "Add Product", "Search Products"]
        )

        if page == "My Products":
            display_user_info(user_tid)
        elif page == "Add Product":
            add_product_form(user_tid)
        elif page == "Search Products":
            product_search(user_tid)

        st.sidebar.markdown("---")
        if st.sidebar.button("Logout"):
            st.session_state["authenticated"] = False
            st.session_state.pop("user_tid", None)
            st.rerun()


if __name__ == "__main__":
    main()