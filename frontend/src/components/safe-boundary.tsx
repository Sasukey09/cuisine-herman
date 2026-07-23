"use client";

import { Component, type ReactNode } from "react";

/** Isole une carte auxiliaire du reste de la page.
 *
 *  Pourquoi : sur la fiche facture, une carte annexe (contrôle, historique…)
 *  qui lève à l'affichage faisait tomber la page ENTIÈRE dans l'écran d'erreur
 *  — l'utilisateur perdait la facture pour un encart secondaire. C'est arrivé
 *  quand la forme d'une réponse API a changé sous un ancien client déployé.
 *
 *  Une carte qui échoue doit disparaître, pas emporter la page avec elle. On
 *  n'affiche rien plutôt qu'un message d'erreur : l'encart est secondaire, son
 *  absence se passe d'explication. */
export class SafeBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return this.props.fallback ?? null;
    return this.props.children;
  }
}
