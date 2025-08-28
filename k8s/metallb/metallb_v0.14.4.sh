kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.4/config/manifests/metallb-native.yaml
# failurePolicy=Ignore로 변경(웹훅은 남겨둔 채 검증만 무시)
kubectl patch validatingwebhookconfiguration metallb-webhook-configuration --type='json' \
  -p='[
    {"op":"replace","path":"/webhooks/0/failurePolicy","value":"Ignore"},
    {"op":"replace","path":"/webhooks/1/failurePolicy","value":"Ignore"},
    {"op":"replace","path":"/webhooks/2/failurePolicy","value":"Ignore"},
    {"op":"replace","path":"/webhooks/3/failurePolicy","value":"Ignore"},
    {"op":"replace","path":"/webhooks/4/failurePolicy","value":"Ignore"},
    {"op":"replace","path":"/webhooks/5/failurePolicy","value":"Ignore"}
  ]'
