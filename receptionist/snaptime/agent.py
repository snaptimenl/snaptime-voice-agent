"""LiveKit wrapper: exposes the Snaptime toolkit as function tools.

Only the tools the Snaptime helpline needs stay visible to the model. The generic receptionist
tools (transfer, messages, intake, calendar, info packets, DTMF) are shadowed by plain methods so
LiveKit does not register them — Snaptime uses callback requests only, never call transfer.
"""
from __future__ import annotations

import time

from livekit.agents import RunContext, function_tool

from receptionist.agent import Receptionist
from receptionist.snaptime.client import SnaptimeClient
from receptionist.snaptime.toolkit import SnaptimeToolkit


class SnaptimeReceptionist(Receptionist):
    def __init__(self, config, lifecycle, client: SnaptimeClient) -> None:
        super().__init__(config, lifecycle)
        self.client = client
        self.started_at = time.monotonic()
        self.toolkit = SnaptimeToolkit(
            client, call_id=lifecycle.metadata.call_id, caller_phone=lifecycle.metadata.caller_phone,
        )

    # --- Snaptime tools -------------------------------------------------

    @function_tool()
    async def lookup_session_by_code(self, ctx: RunContext, code: str) -> str:
        """Zoek de school of het event en de fotograaf op met de inlogcode van een klant.

        Args:
            code: de inlogcode van het inlogkaartje, exact zoals de beller die noemt (letters en cijfers).
        """
        self.toolkit.caller_phone = self.lifecycle.metadata.caller_phone
        return await self.toolkit.lookup_session_by_code(code)

    @function_tool()
    async def identify_photographer(self, ctx: RunContext) -> str:
        """Controleer of de beller een bekende fotograaf is, op basis van het telefoonnummer van de beller."""
        self.toolkit.caller_phone = self.lifecycle.metadata.caller_phone
        return await self.toolkit.identify_photographer()

    @function_tool()
    async def zoek_in_kennisbank(self, ctx: RunContext, vraag: str) -> str:
        """Zoek in de kennisbank/handleiding het antwoord op een vraag over Snaptime. Gebruik dit voor elke vraag
        waarvan het antwoord niet al in je instructies staat.

        Args:
            vraag: de vraag van de beller in een paar woorden, bijvoorbeeld "gratis verzenden instellen".
        """
        return await self.toolkit.zoek_in_kennisbank(vraag)

    @function_tool()
    async def create_callback_request(
        self, ctx: RunContext, caller_name: str, callback_number: str, message: str,
    ) -> str:
        """Leg een terugbelverzoek vast. Klanten worden door hun fotograaf teruggebeld, fotografen door Snaptime.

        Args:
            caller_name: voornaam of naam van de beller.
            callback_number: telefoonnummer om op terug te bellen, ná bevestiging door de beller.
            message: korte omschrijving van de vraag. GEEN namen van personen op de foto's of andere persoonsgegevens.
        """
        return await self.toolkit.create_callback_request(caller_name, callback_number, message)

    # --- generic tools we do NOT expose (plain methods => not registered) ---

    async def transfer_call(self, ctx, department):
        return "Doorverbinden is niet beschikbaar."

    async def take_message(self, *args, **kwargs):
        return "Gebruik create_callback_request."

    async def record_intake_answer(self, *args, **kwargs):
        return "Niet beschikbaar."

    async def await_keypad_entry(self, *args, **kwargs):
        return "Niet beschikbaar."

    async def finalize_intake(self, *args, **kwargs):
        return "Niet beschikbaar."

    async def send_info_packet(self, *args, **kwargs):
        return "Niet beschikbaar."

    async def get_business_hours(self, *args, **kwargs):
        return "Niet beschikbaar."

    async def check_availability(self, *args, **kwargs):
        return "Niet beschikbaar."

    async def book_appointment(self, *args, **kwargs):
        return "Niet beschikbaar."
