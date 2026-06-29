# Gateway middleware

These examples show a host-owned gateway making an allow / block / route
decision before any downstream service call happens.

Context Compiler owns the authoritative policy state.

The host owns the gateway boundary, the default route, and the downstream
handler invocation.

Adversarial wording does not bypass the gateway or mutate authoritative state.

## Examples

### `customer_support_routing`

Routes a host-owned customer support request to `billing_support` only when
authoritative state contains:

```text
use billing_support
```

If state is absent, the gateway blocks billing-routed requests and still allows
non-billing requests to follow the documented default path,
`general_support`.

If state contains:

```text
prohibit billing_support
```

the gateway blocks billing-routed requests before the downstream handler is
called.

The tests cover default-path behavior, authorized routing, blocked routing,
adversarial text, downstream non-invocation when blocked, and contradiction /
clarification behavior.
