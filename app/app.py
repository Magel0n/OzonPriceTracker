import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os
from pathlib import Path
from typing import Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:12345")
STATIC_FILES_URL = os.getenv("STATIC_FILES_URL", "http://localhost:12345/static")

auth_token = st.query_params["token"]
user_tid = None

def load_css():
    css_file = Path(__file__).parent / "static" / "styles.css"
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def make_api_request(endpoint: str, method: str = "GET", data: Optional[dict] = None):
    global auth_token
    
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, json=data, headers=headers)
        else:
            return None, "Invalid HTTP method"

        if response.status_code == 200:
            return response.json(), None
        else:
            error_data = response.json()
            return None, error_data.get("message", "Unknown error occurred")
    except requests.exceptions.RequestException as e:
        return None, f"Connection error: {str(e)}"


def display_user_info():
    global user_tid
    
    data, error = make_api_request(f"/profile")

    if error:
        st.error(f"Failed to load user data: {error}")
        return

    user = data["user"]
    tracked_products = data["tracked_products"]

    user_tid = user["tid"]

    # CSS classes
    st.markdown(
        f"""
        <div class="profile-container">
            <img src="{STATIC_FILES_URL}/profile-pictures/{user['tid'] if user['user_pfp'] else 'https://via.placeholder.com/100'}" 
                 width="100" class="profile-image">
            <div>
                <h2>{user['name']}</h2>
                <p>@{user['username']}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Tracked products
    st.header("📊 Your Tracked Products")
    if not tracked_products:
        st.info("You are not tracking any products yet.")
    else:
        for product in tracked_products:
            with st.expander(f"🛍️ {product['name']} - 💰 {product['price']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Seller:** {product['seller']}")
                    st.markdown(f"**URL:** [{product['url']}]({product['url']})")
                    st.markdown(f"**Alert Threshold:** ${product['tracking_price']}")

                with col2:
                    with st.form(key=f"threshold_{product['product_id']}"):
                        new_threshold = st.text_input(
                            "Update Threshold",
                            value=product["tracking_price"],
                            key=f"input_{product['product_id']}"
                        )
                        if st.form_submit_button("💾 Save"):
                            update_data = {
                                "user_tid": user_tid,
                                "product_id": product["product_id"],
                                "new_price": new_threshold
                            }
                            _, error = make_api_request("/tracking", "PUT", update_data)
                            if error:
                                st.error(f"Error: {error}")
                            else:
                                st.success("Threshold updated!")
                                st.rerun()

                    if st.button("🗑️ Stop Tracking", key=f"delete_{product['product_id']}"):
                        delete_data = {
                            "user_tid": user_tid,
                            "product_id": product["product_id"]
                        }
                        _, error = make_api_request("/tracking", "DELETE", delete_data)
                        if error:
                            st.error(f"Error: {error}")
                        else:
                            st.success("Product removed from tracking")
                            st.rerun()

                # Price history visualization
                st.subheader("📈 Price History")
                history_data, error = make_api_request(f"/product/{product['product_id']}/history")
                if error:
                    st.warning(f"Couldn't load history: {error}")
                elif history_data["history"]:
                    df = pd.DataFrame(history_data["history"], columns=["timestamp", "price"])
                    df["price"] = df["price"].astype(float)
                    df["date"] = pd.to_datetime(df["timestamp"], unit="s")

                    fig = px.line(
                        df, x="date", y="price",
                        color_discrete_sequence=["#005BFF"],
                        title="",
                        labels={"price": "Price ($)", "date": "Date"}
                    )
                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No price history available")


def add_product_form(user_tid: str):
    with st.form(key="add_product_form"):
        st.header("➕ Add New Product")

        method = st.radio(
            "Add by:",
            ("🔗 Product URL", "🏷️ Product SKU"),
            horizontal=True
        )

        if method == "🔗 Product URL":
            product_url = st.text_input("Product URL")
            product_sku = None
        else:
            product_sku = st.text_input("Product SKU")
            product_url = None

        price_threshold = st.text_input("💰 Price Alert Threshold")

        if st.form_submit_button("🚀 Start Tracking"):
            if not (product_url or product_sku):
                st.error("Please provide URL or SKU")
            elif not price_threshold:
                st.error("Please set price threshold")
            else:
                tracking_data = {
                    "user_tid": user_tid,
                    "product_url": product_url,
                    "product_sku": product_sku
                }

                response, error = make_api_request("/tracking", "POST", tracking_data)
                if error:
                    st.error(f"Error: {error}")
                else:
                    # Set threshold after adding
                    update_data = {
                        "user_tid": user_tid,
                        "product_id": response["product_id"],
                        "new_price": price_threshold
                    }
                    _, error = make_api_request("/tracking", "PUT", update_data)
                    if error:
                        st.error(f"Added but couldn't set threshold: {error}")
                    else:
                        st.success("Product added successfully!")
                        st.rerun()


def login_page():
    st.title("Product Price Tracker")

    with st.form(key="login_form"):
        user_tid = st.text_input("Enter Your Telegram User ID")
        if st.form_submit_button("Login"):
            if user_tid:
                st.session_state["user_tid"] = user_tid
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Please enter your User ID")


def product_search(user_tid: str):
    """Search and filter products with themed UI."""
    st.header("🔍 Product Search")

    # Search inputs with themed styling
    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input(
            "Search by product name or seller",
            help="Enter keywords to find products"
        )

    with col2:
        price_range = st.slider(
            "Price range",
            min_value=0.0,
            max_value=1000.0,
            value=(0.0, 1000.0),
            step=1.0,
            format="$%.2f"
        )

    # Search button with gradient styling
    if st.button(
            "🔎 Search Products",
            use_container_width=True,
            type="primary"  # Uses the primary color from our theme
    ):
        if search_query or price_range != (0.0, 1000.0):
            # Когда бэк доделаете подклбчите
            # make_api_request("/search", "POST", {
            #     "query": search_query,
            #     "min_price": price_range[0],
            #     "max_price": price_range[1]
            # })

            # Показывает пока просто всякое
            st.info(f"Searching for: '{search_query}' between ${price_range[0]:.2f}-${price_range[1]:.2f}")

            demo_results = [
                {"name": "Premium Headphones", "price": "199.99", "seller": "AudioTech"},
                {"name": "Wireless Earbuds", "price": "89.99", "seller": "SoundMaster"},
                {"name": "Bluetooth Speaker", "price": "129.99", "seller": "AudioTech"}
            ]

            # Display results with themed cards
            for product in demo_results:
                with st.container(border=True):
                    cols = st.columns([3, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{product['name']}**")
                        st.caption(f"Seller: {product['seller']}")
                    with cols[1]:
                        st.markdown(f"${product['price']}")
                    with cols[2]:
                        if st.button(
                                "Track",
                                key=f"track_{product['name']}",
                                help=f"Track price for {product['name']}"
                        ):
                            # In real app: call add_tracking API
                            st.success(f"Added {product['name']} to tracked products!")
                            st.rerun()
        else:
            st.warning("Please enter search criteria or adjust price range")

def main():
    global user_tid

    st.set_page_config(
        page_title="Product Tracker",
        page_icon="🛒",
        layout="wide"
    )
    load_css()

    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        login_page()
    else:
        user_tid = st.session_state["user_tid"]

        st.sidebar.title("🎨 Menu")
        page = st.sidebar.radio(
            "Navigation",
            ["📦 My Products", "➕ Add Product", "🔍 Search Products"]
        )

        if page == "📦 My Products":
            display_user_info()
        elif page == "➕ Add Product":
            add_product_form(user_tid)
        elif page == "🔍 Search Products":
            product_search(user_tid)

        if st.sidebar.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()


if __name__ == "__main__":
    main()