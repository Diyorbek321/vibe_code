"""
FSM states for multi-turn conversations.
"""
from aiogram.fsm.state import State, StatesGroup


class TransactionFSM(StatesGroup):
    """
    States for the transaction entry flow.

    waiting_clarification: bot has asked a follow-up question and is waiting
                           for the user to provide the missing information.
    confirming:            bot has extracted a transaction and is waiting for
                           the user to confirm or cancel saving it.
    editing_field:         user chose to edit last transaction — waiting for
                           field selection (amount / category / description).
    editing_value:         waiting for the new value for the chosen field.
    """
    waiting_clarification = State()
    confirming = State()
    editing_field = State()
    editing_value = State()


class RegistrationFSM(StatesGroup):
    """States for the /start inline registration flow."""
    waiting_full_name    = State()
    waiting_company_name = State()
    waiting_email        = State()
    waiting_password     = State()
