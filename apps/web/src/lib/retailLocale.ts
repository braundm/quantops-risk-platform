// Keep user-facing explanations separate from numerical calculation contracts.
export const retailLocales = {
  pl: {
    title: "Zrozum swój portfel.",
    subtitle: "Zobacz ekspozycje i sprawdź konsekwencje zmian, zanim podejmiesz decyzję.",
    warnings: {
      quotation_currency_only: "Waluta notowania nie oznacza pełnej ekspozycji ekonomicznej. Brak look-through aktywów ETF.",
      no_historical_returns: "Brak historii cen i przepływów. VaR, ES, zmienność i wyniki inwestora są niedostępne dla tego portfela.",
      terminal_forward_model: "Forward: model rozliczenia w terminie, bez dyskontowania wyniku. Nie obejmuje depozytu, płynności ani ryzyka kontrahenta.",
      user_cost_estimates: "Koszty są założeniami użytkownika. Opłaty produktowe, podatki i koszty zmiany alokacji nie są tu wyliczane.",
      no_broker_quote: "Kurs forward jest teoretyczny, wyliczony z podanych stóp. Nie jest ofertą brokera. CFD i ETF nie są równoważnym zabezpieczeniem.",
      cash_entered_once: "Gotówka jest osobną pozycją. Nie dodawaj równocześnie wartości całego rachunku.",
      stale_prices: "Ceny są starsze niż 24 godziny. Wynik odnosi się do wpisanej wyceny, nie do bieżącego rynku.",
      stale_fx: "Kursy walut są starsze niż 24 godziny. Uzupełnij je przed analizą aktualnego portfela.",
      nonpositive_equity: "Wartość netto nie jest dodatnia. Procentowy wpływ i relacja ekspozycji do kapitału są niedostępne.",
      short_collateral_excluded: "Portfel zawiera pozycje krótkie. Model nie obejmuje depozytu ani kosztów pożyczki papierów.",
    } as Record<string, string>,
  },
};
