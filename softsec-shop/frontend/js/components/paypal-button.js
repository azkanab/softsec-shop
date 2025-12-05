const container = document.getElementById('paypal-button-container');
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
const orderToken = container.dataset.orderToken;

window.paypal
.Buttons({
    style: {
        shape: "rect",
        layout: "vertical",
        color: "gold",
        label: "paypal",
    },

    // Task 3.5 Step 1: Fetch from our API in file order/views.py to call paypal_pay function to create order in Paypal
    async createOrder() {
        try {
            const response = await fetch(`/orders/pay/${orderToken}/paypal`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
                body: JSON.stringify({
                token: orderToken
                }),
            });

            const orderData = await response.json();

            if (orderData.id) {
                return orderData.id;
            }
            const errorDetail = orderData?.details?.[0];
            const errorMessage = errorDetail
            ? `${errorDetail.issue} ${errorDetail.description} (${orderData.debug_id})`
            : JSON.stringify(orderData);

            throw new Error(errorMessage);
        } catch (error) {
            console.error(error);
            alert(`Could not initiate PayPal Checkout, please try again later. Error: ${error}`);
        }
    },

    // Task 3.5 Step 2: Fetch from our API in file order/views.py to call paypal_notify function to finalize/capture payment in Paypal
    async onApprove(data, actions) {
        try {
            const response = await fetch(`/orders/paypal/gateway/${data.orderID}/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },
            });

            const orderData = await response.json();
            // Three cases to handle:
            //   (1) Recoverable INSTRUMENT_DECLINED -> call actions.restart()
            //   (2) Other non-recoverable errors -> Show a failure message
            //   (3) Successful transaction -> Show confirmation or thank you message

            const errorDetail = orderData?.details?.[0];

            if (errorDetail?.issue === "INSTRUMENT_DECLINED") {
                // (1) Recoverable INSTRUMENT_DECLINED -> call actions.restart()
                // recoverable state, per
                // https://developer.paypal.com/docs/checkout/standard/customize/handle-funding-failures/
                return actions.restart();
            } else if (errorDetail) {
                // (2) Other non-recoverable errors -> Show a failure message
                throw new Error(`${errorDetail.description} (${orderData.debug_id})`);
            } else if (!orderData.purchase_units) {
                throw new Error(JSON.stringify(orderData));
            } else {
                // (3) Successful transaction -> Show confirmation or thank you message
                // Or go to another URL:  actions.redirect('thank_you.html');
                actions.redirect(orderData.redirect_url)
            }
        } catch (error) {
            console.error(error);
            alert(`Sorry, your PayPal transaction could not be processed... Please try again later. Error: ${error}`);
        }
    },
})
.render("#paypal-button-container");

// Showing error to the users
function errorMessage(message) {
  const container = document.querySelector("#error-message");
  container.innerHTML = message;
}