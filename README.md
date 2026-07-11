## Description

Zero-trust microservices on Kubernetes with multi-agent security scoring, automatic context failover, and adaptive service composition.

## Overview

A zero-trust microservices platform deployed on Kubernetes, built around a multi-agent system (MAS) that continuously evaluates service security and automatically reroutes traffic when a deployment context becomes compromised.

## Technical Stack
* Kubernetes (Minikube)
* Istio (mTLS)
* Keycloak (identités)
* OPA (autorisation)
* Falco (runtime security)
* Sealed Secrets (gestion des secrets)
* Prometheus + Grafana (observabilité)
* Python (agents LSA et CCA)

## Final Results

<pre><span style="color:#00AA00"><b>asus@Pharah</b></span>:<span style="color:#0000AA"><b>~/zero-trust-microservices/tests</b></span>$ ./demo_soutenance.sh 
<span style="color:#00AA00">=== DÉMO ZERO-TRUST MAS ===</span>

<span style="color:#00AA00">[SCÉNARIO 1] État nominal</span>
  service-payment:ctx-b = 0.97
  service-auth:ctx-a = 0.7384
  service-orders:ctx-a = 0.7384
  service-notification:ctx-a = 0.7384

<span style="color:#AA5500"><b>[SCÉNARIO 2] Injection score sain ctx-b (secours prêt)</b></span>
  ctx-b HEALTHY (score=0.97) injecté
<span style="color:#AA0000">[SCÉNARIO 3] Attaque simulée sur service-payment:ctx-a</span>
  ctx-a CRITICAL (score=0.28) injecté

<span style="color:#00AA00">[RÉSULTAT] Vérification du basculement</span>
  Selector actif : ctx-b
  Contexte actif : ctx-b
  ctx-a isolé : True
  ctx-b score : 0.97
  Basculement : ctx-a -&gt; ctx-b à 2026-07-11T22:59:40.462229

<span style="color:#00AA00">[SCÉNARIO 4] Composition workflow checkout</span>
  Services sélectionnés : 4
     service-payment [ctx-b] score=0.97
     service-auth [ctx-a] score=0.7384
     service-orders [ctx-a] score=0.7384
     service-notification [ctx-a] score=0.7384

<span style="color:#00AA00">=== FIN DÉMO ===</span>
</pre>
