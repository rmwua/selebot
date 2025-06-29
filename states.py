from aiogram.fsm.state import StatesGroup, State


class RequestCelebrity(StatesGroup):
    waiting_for_info = State()


class SearchMenu(StatesGroup):
    choosing_method = State()
    choosing_geo    = State()
    choosing_cat    = State()
    entering_name   = State()
    manual_entry    = State()


class EditCelebrity(StatesGroup):
    choosing_field = State()
    editing_name = State()
    editing_param = State()
    deleting_entry = State()


class EditUserRole(StatesGroup):
    waiting_for_id = State()
    waiting_for_role_choice = State()
