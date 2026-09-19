"""Engine-independent Snaptime tools. Each returns a short Dutch instruction/answer for the model."""
from __future__ import annotations

from .client import SnaptimeClient

MAX_WRONG_CODES = 3

_ENTITLEMENT_FALLBACK = (
    "Deze klantenservice is voor deze fotograaf niet beschikbaar. Zeg vriendelijk dat je niet kunt helpen "
    "en verwijs de beller naar de fotograaf zelf of naar de gegevens op de website. Beëindig daarna het gesprek."
)


class SnaptimeToolkit:
    def __init__(self, client: SnaptimeClient, *, call_id: str, caller_phone: str | None) -> None:
        self.client = client
        self.call_id = call_id
        self.caller_phone = caller_phone
        self._wrong_codes = 0
        self.caller_kind: str | None = None  # 'ouder' | 'fotograaf'

    async def lookup_session_by_code(self, code: str) -> str:
        if self._wrong_codes >= MAX_WRONG_CODES:
            return "Te veel foute codes. Zeg dat je de code niet kunt controleren en bied aan om een terugbelverzoek achter te laten zonder code is NIET mogelijk; beëindig vriendelijk het gesprek."
        res = await self.client.lookup_session_by_code(call_id=self.call_id, code=code)
        if res is None:
            return "Technische storing bij het opzoeken van de code. Verontschuldig je en vraag de beller het later nog eens te proberen."
        if not res.get("found"):
            self._wrong_codes += 1
            return "Deze code is niet gevonden. Vraag of de beller de code nog eens langzaam wil doorgeven, teken voor teken."
        if not res.get("entitled"):
            return _ENTITLEMENT_FALLBACK
        self.caller_kind = "ouder"
        return (
            f"Code herkend: school of event '{res.get('schoolNaam')}', fotograaf '{res.get('photographerName')}'. "
            "Bevestig dit kort aan de beller (alleen school of event en fotograaf, geen namen van personen) en vraag waarmee je kunt helpen."
        )

    async def identify_photographer(self) -> str:
        if not self.caller_phone:
            return "Het nummer van de beller is niet zichtbaar; de beller kan niet als fotograaf worden herkend."
        res = await self.client.identify_photographer(call_id=self.call_id, caller_number=self.caller_phone)
        if res is None:
            return "Technische storing bij het herkennen van de beller."
        if not res.get("found"):
            return "Dit nummer hoort niet bij een bekende fotograaf. Behandel de beller als klant en vraag naar de inlogcode."
        if not res.get("entitled"):
            return _ENTITLEMENT_FALLBACK
        self.caller_kind = "fotograaf"
        return (
            f"Beller herkend als fotograaf '{res.get('photographerName')}'. Begroet met naam en vraag waarmee je kunt helpen. "
            "Het nummer kan vervalst zijn: geef geen accountgegevens, alleen uitleg en hulp."
        )

    async def zoek_in_kennisbank(self, vraag: str) -> str:
        res = await self.client.search_knowledge(call_id=self.call_id, query=vraag)
        if res is None:
            return "De kennisbank is nu niet bereikbaar. Zeg dat en bied een terugbelverzoek aan."
        results = res.get("results") or []
        if not results:
            return (
                "Niets gevonden in de kennisbank. Zeg eerlijk dat je het niet zeker weet, verzin niets en bied een "
                "terugbelverzoek aan."
            )
        passages = "\n\n".join(f"Vraag: {r['question']}\nAntwoord: {r['answer']}" for r in results)
        return (
            "Beantwoord de vraag alleen op basis van deze passages, kort en als gesproken stappen. "
            "Past geen enkele passage bij de vraag, zeg dan dat je het niet zeker weet.\n\n" + passages
        )

    async def create_callback_request(self, caller_name: str, callback_number: str, message: str) -> str:
        res = await self.client.create_callback_request(
            call_id=self.call_id, caller_name=caller_name or None, callback_number=callback_number, message=message,
        )
        if res is None:
            return "Het vastleggen is mislukt door een storing. Verontschuldig je en vraag de beller het later nog eens te proberen."
        if res.get("ok"):
            who = "Snaptime" if res.get("target") == "snaptime" else "de fotograaf"
            return f"Terugbelverzoek vastgelegd. Zeg dat {who} zo snel mogelijk terugbelt en vraag of je nog iets kunt doen."
        reason = res.get("reason")
        if reason == "ongeldig_nummer":
            return "Het telefoonnummer lijkt niet te kloppen. Vraag het nummer opnieuw en lees het cijfer voor cijfer terug."
        if reason == "beller_niet_herkend":
            return "Zonder herkende inlogcode of fotograaf kan geen terugbelverzoek worden vastgelegd. Vraag eerst de inlogcode."
        return _ENTITLEMENT_FALLBACK
