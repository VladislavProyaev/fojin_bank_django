class EndPoints:
    __main_service_name = 'core_'

    REGISTRATION = __main_service_name + 'user_registration'
    AUTHORIZATION = __main_service_name + 'user_authorization'
    VALIDATE_ACTION = __main_service_name + 'user_handler_action'
    REFRESH_TOKEN = __main_service_name + 'refresh_access_token'
