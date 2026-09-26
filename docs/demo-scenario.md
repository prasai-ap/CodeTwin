# Payment Authorization Regression Scenario

## 1. Original workflow

The baseline payment service moved a new payment directly from `pending` to `completed`. The order service then completed the associated order and requested a payment-completion notification.

## 2. Proposed change

The payment flow now authorizes a pending payment before it completes it. This models a common payment-provider workflow where approval and capture are separate states.

## 3. New workflow

`pending → authorized → completed`

The payment service persists and forwards both transitions.

## 4. Affected components

- `demo-project/app/models/payment.py` adds the `authorized` state.
- `demo-project/app/payments/lifecycle.py` defines authorization and completion transitions.
- `demo-project/app/services/payments_service.py` applies both transitions.
- `demo-project/app/services/orders_service.py` receives each transition, completes the order after payment completion, and forwards the event.
- `demo-project/app/services/notifications_service.py` consumes payment transitions.
- `demo-project/app/api/payments.py` exposes the payment completion operation.

## 5. Downstream dependency

The call path is `Payment API → PaymentsService → OrdersService → NotificationsService`. The notification service retains its original event contract: it sends a completion notification only when it sees `pending → completed` in one transition.

## 6. Expected regression

The notification service receives `pending → authorized` followed by `authorized → completed`. Neither transition matches its old condition. The payment and order complete, but the user receives no `payment_completed` notification.

## 7. Relevant tests

- `demo-project/tests/test_payment_workflow.py` checks that payment and order completion still work.
- `demo-project/tests/test_payment_authorization_regression.py::test_completed_payment_emits_payment_completed_notification` checks the downstream notification contract.
- The remaining demo-project tests cover auth, users, products, order creation, health, and payment access.

## 8. Expected failure

The focused regression test fails at the assertion that a matching `payment_completed` notification exists. That is the intended, deterministic failure; the API call, payment transition, and order transition still succeed. All other tests should pass.

## 9. Intended fix

Update the notification consumer to recognize completion after authorization, for example by reacting to any transition whose current payment state is `completed` (with an idempotency guard if events can be delivered more than once). Then rerun the targeted test and full demo-project suite before considering the workflow safe.
