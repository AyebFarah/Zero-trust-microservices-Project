#!/bin/bash
# Script de démonstration — Soutenance Zero-Trust MAS

CCA="http://localhost:8080"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== DÉMO ZERO-TRUST MAS ===${NC}"
echo ""

# Scénario 1 : État nominal
echo -e "${GREEN}[SCÉNARIO 1] État nominal${NC}"
curl -s "$CCA/api/status" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for svc, info in d['services'].items():
    ctx = info['active_context']
    score = info['contexts'][ctx].get('score', 'N/A')
    print(f'  {svc}:{ctx} = {score}')
"
echo ""
sleep 2

# Scénario 2 : Injection score sain ctx-b
echo -e "${YELLOW}[SCÉNARIO 2] Injection score sain ctx-b (secours prêt)${NC}"
curl -s -X POST "$CCA/api/scores" \
  -H "Content-Type: application/json" \
  -d "{\"service\":\"service-payment:ctx-b\",\"score\":0.97,\"components\":{\"C\":1.0,\"I\":1.0,\"B\":1.0,\"P\":1.0,\"R\":1.0},\"status\":\"HEALTHY\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S)\"}" > /dev/null
echo "  ctx-b HEALTHY (score=0.97) injecté"
sleep 1

# Scénario 3 : Attaque simulée
echo -e "${RED}[SCÉNARIO 3] Attaque simulée sur service-payment:ctx-a${NC}"
curl -s -X POST "$CCA/api/scores" \
  -H "Content-Type: application/json" \
  -d "{\"service\":\"service-payment:ctx-a\",\"score\":0.28,\"components\":{\"C\":0.20,\"I\":0.15,\"B\":0.10,\"P\":0.80,\"R\":0.30},\"status\":\"CRITICAL\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S)\"}" > /dev/null
echo "  ctx-a CRITICAL (score=0.28) injecté"
sleep 3

# Vérifier le basculement
echo ""
echo -e "${GREEN}[RÉSULTAT] Vérification du basculement${NC}"
CONTEXT=$(kubectl get svc service-payment -n app -o jsonpath='{.spec.selector.context}' 2>/dev/null)
echo "  Selector actif : $CONTEXT"
curl -s "$CCA/api/routing" | python3 -c "
import json,sys
d=json.load(sys.stdin)
svc = d['routing']['service-payment']
print(f'  Contexte actif : {svc[\"active_context\"]}')
print(f'  ctx-a isolé : {svc[\"contexts\"][\"ctx-a\"][\"isolated\"]}')
print(f'  ctx-b score : {svc[\"contexts\"][\"ctx-b\"][\"score\"]}')
h = d['routing_history']
if h:
    last = h[-1]
    print(f'  Basculement : {last[\"from_context\"]} -> {last[\"to_context\"]} à {last[\"timestamp\"]}')
"
echo ""

# Scénario 4 : Composition workflow
echo -e "${GREEN}[SCÉNARIO 4] Composition workflow checkout${NC}"
curl -s "$CCA/api/compose?workflow=checkout" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f'  Services sélectionnés : {len(d[\"selected\"])}')
for s in d['selected']:
    print(f'     {s[\"service\"]} [{s.get(\"context\",\"?\")}] score={s[\"score\"]}')
for e in d['excluded']:
    print(f'     {e[\"service\"]} — {e[\"reason\"]}')
"
echo ""
echo -e "${GREEN}=== FIN DÉMO ===${NC}"
