import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import os
from pathlib import Path
from typing import Optional

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:12345")
STATIC_FILES_URL = os.getenv("STATIC_FILES_URL",
                             "http://localhost:12345/static")

TG_BOT_LINK = "https://t.me/priceTrackerOzonBot"

# Initialize session state
if "user_tid" not in st.session_state:
    st.session_state.user_tid = None
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None


def load_css():
    css_file = Path(__file__).parent / "static" / "styles.css"
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def make_api_request(endpoint: str, method: str = "GET",
                     data: Optional[dict] = None):
    if not st.session_state.auth_token:
        return None, "Not authenticated"

    url = f"{API_BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {st.session_state.auth_token}"}
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url,
                                     json=data,
                                     headers=headers,
                                     timeout=10)
        elif method.upper() == "PUT":
            response = requests.put(url,
                                    json=data,
                                    headers=headers,
                                    timeout=10)
        elif method.upper() == "DELETE":
            response = requests.delete(url,
                                       json=data,
                                       headers=headers,
                                       timeout=10)
        else:
            return None, "Invalid HTTP method"

        if response.status_code == 200:
            return response.json(), None
        elif response.status_code == 401:  # Unauthorized
            return (None,
                    'Unauthorized - please login'
                    + ' via Telegram bot {TG_BOT_LINK}')
        else:
            error_data = response.json()
            return None, error_data.get("message", "Unknown error occurred")
    except requests.exceptions.RequestException as e:
        return None, f"Connection error: {str(e)}"
    except requests.exceptions.Timeout as e:
        return None, f"Connection time out: {str(e)}"


def check_auth():
    query_params = st.query_params.to_dict()
    if "token" in query_params and not st.session_state.auth_token:
        st.session_state.auth_token = query_params["token"]
        # Verify token with backend
        data, error = make_api_request("/verify-token")
        if error:
            st.session_state.auth_token = None
            return False
        st.session_state.user_tid = data.get("user_tid")
        return True
    return st.session_state.auth_token is not None


def auth_gate():
    st.title("🔒 Product Price Tracker")
    st.markdown(f"""
    <div style="text-align: center; margin-top: 50px;">
        <h3>Please login via our Telegram bot</h3>
        <a href="{TG_BOT_LINK}" target="_blank">
            <button style="background-color: #005BFF;
            color: white;
            border: none;
                         padding: 10px 20px;
                         border-radius: 5px; cursor: pointer;
                         font-size: 16px;">
                Login with Telegram
            </button>
        </a>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


def display_user_info():
    data, error = make_api_request("/profile")

    if error:
        st.error(f"Failed to load user data: {error}")
        return

    user = data["user"]
    tracked_products = data["tracked_products"]

    # CSS classes
    filename = f"{user['user_pfp']}.jpg" if user['user_pfp'] else 'default.jpg'
    upp = "UserProfilePictures"
    st.markdown(
        f"""
        <div class="profile-container">
            <img src="{STATIC_FILES_URL}/{upp}/{filename}"
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
            with (st.expander(f"🛍️ {product['name']} - 💰 {product['price']}")):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Seller:** {product['seller']}")
                    st.markdown(f"**URL:** [{product['url']}]"
                                + "({product['url']})")
                    st.markdown("**Alert Threshold:** "
                                + f"₽{product['tracking_price']}")

                with col2:
                    with st.form(key=f"threshold_{product['id']}"):
                        new_threshold = st.text_input(
                            "Update Threshold",
                            value=product["tracking_price"],
                            key=f"input_{product['id']}"
                        )
                        if st.form_submit_button("💾 Save"):
                            update_data = {
                                "user_tid": st.session_state.user_tid,
                                "product_id": product["id"],
                                "new_price": new_threshold
                            }
                            _, error = make_api_request("/tracking",
                                                        "PUT", update_data)
                            if error:
                                st.error(f"Error: {error}")
                            else:
                                st.success("Threshold updated!")
                                st.rerun()

                    if st.button("🗑️ Stop Tracking",
                                 key=f"delete_{product['id']}"):
                        delete_data = {
                            "user_tid": st.session_state.user_tid,
                            "product_id": product["id"]
                        }
                        _, error = make_api_request("/tracking",
                                                    "DELETE", delete_data)
                        if error:
                            st.error(f"Error: {error}")
                        else:
                            st.success("Product removed from tracking")
                            st.rerun()

                # Price history visualization
                st.subheader("📈 Price History")
                path = f"/product/{product['id']}/history"
                history_data, error = make_api_request(path)
                if error:
                    st.warning(f"Couldn't load history: {error}")
                elif history_data["history"]:
                    df = pd.DataFrame(history_data["history"],
                                      columns=["timestamp", "price"])
                    df["price"] = df["price"].astype(float)
                    df["date"] = pd.to_datetime(df["timestamp"], unit="s")

                    fig = px.line(
                        df, x="date", y="price",
                        color_discrete_sequence=["#005BFF"],
                        title="",
                        labels={"price": "Price (₽)", "date": "Date"}
                    )
                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No price history available")


def add_product_form(user_tid: str):
    """Form to add a new product to track."""
    st.subheader("Add New Product to Track")

    method = st.radio(
        "Add by:",
        ("Product URL", "SKU"),
        horizontal=True
    )

    # Dynamic label based on selection
    if method == "Product URL":
        input_label = "Product URL"
    else:
        input_label = "Product SKU"

    product_identifier = st.text_input(input_label)  # Updated label

    price_threshold = st.text_input("Notify me when price drops below")

    with st.form(key="add_product_form"):
        submitted = st.form_submit_button("Start Tracking")
        if submitted:
            if not product_identifier:
                st.error(f"Please provide a {input_label}")
                return

            if not price_threshold:
                st.error("Please set a price threshold")
                return

            tracking_data = {
                "user_tid": user_tid,
                "product_url": product_identifier if method == "Product URL"
                else None,
                "product_sku": product_identifier if method == "SKU"
                else None
            }

            response, error = make_api_request("/tracking",
                                               "POST",
                                               tracking_data)
            if error:
                st.error(f"Error: {error}")
            else:
                # Set threshold after adding
                update_data = {
                    "user_tid": user_tid,
                    "product_id": response["id"],
                    "new_price": price_threshold
                }
                _, error = make_api_request("/tracking", "PUT", update_data)
                if error:
                    st.error(f"Added but couldn't set threshold: {error}")
                else:
                    st.success("Product added successfully!")
                    st.rerun()


def product_search(user_tid: str):
    st.header("🔍 Product Search")

    # Search inputs with themed styling
    col1, col2 = st.columns(2)
    with col1:
        search_query_name = st.text_input(
            "Search by product name",
            help="Enter keywords to find products based on its name"
        )
        search_query_seller = st.text_input(
            "Search by product seller",
            help="Enter keywords to find products based on its seller name"
        )

    with col2:
        price_range = st.slider(
            "Price range",
            min_value=0.0,
            max_value=1000.0,
            value=(0.0, 1000.0),
            step=1.0,
            format="₽%.2f"
        )

    # Search button with gradient styling
    if st.button(
            "🔎 Search Products",
            use_container_width=True,
            type="primary"  # Uses the primary color from our theme
    ):
        if (search_query_name or search_query_seller
                or price_range != (0.0, 1000.0)):
            # Когда бэк доделаете подклбчите
            # make_api_request("/search", "POST", {
            #     "query": search_query,
            #     "min_price": price_range[0],
            #     "max_price": price_range[1]
            # })

            # Показывает пока просто всякое
            st.info(
                f"Searching for: name like '{search_query_name}', " +
                f"seller like '{search_query_seller}' and price between " +
                f"₽{price_range[0]:.2f}-₽{price_range[1]:.2f}")

            demo_results = [
                {"name": "Premium Headphones",
                 "price": "199.99",
                 "seller": "AudioTech"},
                {"name": "Wireless Earbuds",
                 "price": "89.99",
                 "seller": "SoundMaster"},
                {"name": "Bluetooth Speaker",
                 "price": "129.99",
                 "seller": "AudioTech"}
            ]

            # Display results with themed cards
            for product in demo_results:
                if not (price_range[0] <= float(product['price'])
                        <= price_range[1]):
                    continue
                if search_query_name and (search_query_name.lower()
                                          not in product['name'].lower()):
                    continue
                if (search_query_seller and search_query_seller.lower()
                        not in product['seller'].lower()):
                    continue
                with st.container(border=True):
                    cols = st.columns([3, 1, 1])
                    with cols[0]:
                        st.markdown(f"{product['name']}")
                        st.caption(f"Seller: {product['seller']}")
                    with cols[1]:
                        st.markdown(f"₽{product['price']}")
                    with cols[2]:
                        if st.button(
                                "Track",
                                key=f"track_{product['name']}",
                                help=f"Track price for {product['name']}"
                        ):
                            # In real app: call add_tracking API
                            st.success(f"Added {product['name']}"
                                       + " to tracked products!")
                            st.rerun()
        else:
            st.warning("Please enter search criteria or adjust price range")


def main():
    st.set_page_config(
        page_title="Product Tracker",
        page_icon="🛒",
        layout="wide"
    )
    load_css()

    if not check_auth():
        auth_gate()

    st.sidebar.title("🎨 Menu")
    page = st.sidebar.radio(
        "Navigation",
        ["📦 My Products", "➕ Add Product", "🔍 Search Products"]
    )

    if page == "📦 My Products":
        display_user_info()
    elif page == "➕ Add Product":
        add_product_form(st.session_state.user_tid)
    elif page == "🔍 Search Products":
        product_search(st.session_state.user_tid)

    if st.sidebar.button("🚪 Logout"):
        make_api_request("/logout")
        st.session_state.clear()
        st.rerun()


if __name__ == "__main__":
    main()
