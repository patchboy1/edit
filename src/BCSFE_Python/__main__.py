import os
import sys
import traceback

from . import (
    adb_handler,
    config_manager,
    feature_handler,
    game_data_getter,
    helper,
    parse_save,
    patcher,
    serialise_save,
    server_handler,
    user_info,
    updater,
    user_input_handler,
    root_handler,
    locale_handler,
)
from .edits.levels import clear_tutorial


def main():
    """Main function"""
    if config_manager.get_config_value_category("SERVER", "WIPE_TRACKED_ITEMS_ON_START"):
        user_info.UserInfo.clear_all_items()
    game_data_getter.check_remove_handler()

    # 감사인사 / 업데이트 확인 등 제거
    normal_start_up()


def normal_start_up(default_op: bool = True) -> None:
    """Display and handle options for downloading save data, pulling save data, selecting save data"""
    default_start_option = config_manager.get_config_value_category("START_UP", "DEFAULT_START_OPTION")
    locale_manager = locale_handler.LocalManager.from_config()

    if default_start_option != -1 and default_op:
        index = default_start_option - 1
    else:
        print()  # 기본적으로 한 줄 공백만 출력
        options = [
            locale_manager.search_key("download_save"),
            locale_manager.search_key("select_save_file"),
            locale_manager.search_key("adb_pull_save"),
            locale_manager.search_key("load_save_data_json"),
        ]
        if helper.is_android():
            options[2] = locale_manager.search_key("android_direct_pull")
        index = (
            user_input_handler.select_single(
                options, 
                title=locale_manager.search_key("select_save_option_title")
            ) - 1
        )

    path = None
    if index == 0:
        helper.colored_text(locale_manager.search_key("data_transfer_message_enter"))
        path = server_handler.download_handler()
    elif index == 1:
        helper.colored_text(locale_manager.search_key("select_save_file_message"))
        path = helper.select_file(
            locale_manager.search_key("select_save_file_message"),
            helper.get_save_file_filetype(),
            initial_file=helper.get_save_path_home(),
        )
    elif index == 2:
        if not helper.is_android():
            helper.colored_text(locale_manager.search_key("adb_pull_message_enter"))
            game_versions = adb_handler.find_game_versions()
            if not game_versions:
                game_version = helper.ask_cc()
            else:
                index = (
                    user_input_handler.select_single(
                        game_versions,
                        locale_manager.search_key("select_l"),
                        locale_manager.search_key("pull_game_version_select"),
                        True,
                    ) - 1
                )
                game_version = game_versions[index]
            path = adb_handler.adb_pull_save_data(game_version)
        else:
            game_versions = root_handler.get_installed_battlecats_versions()
            if game_versions is not None:
                index = (
                    user_input_handler.select_single(
                        game_versions,
                        locale_manager.search_key("select_l"),
                        locale_manager.search_key("pull_game_version_select"),
                        True,
                    ) - 1
                )
                game_version = game_versions[index]
                path = root_handler.pull_save_data(game_version)
    elif index == 3:
        helper.colored_text(locale_manager.search_key("json_save_data_json_message"))
        js_path = helper.select_file(
            locale_manager.search_key("json_save_data_json_message"),
            [("Json", "*.json")],
            initial_file=helper.get_save_path_home() + ".json",
        )
        if js_path:
            path = helper.load_json_handler(js_path)
    else:
        helper.colored_text(locale_manager.search_key("error_option"), base=helper.RED)
        return normal_start_up(False)

    if not path:
        return normal_start_up(False)
    start(path)


def start(path: str) -> None:
    """Parse, patch, start the editor and serialise the save data"""
    locale_manager = locale_handler.LocalManager.from_config()

    if path.endswith(".json"):
        user_input_handler.colored_input(
            f"{locale_manager.search_key('error_save_json')}\n&{locale_manager.search_key('press_enter')}",
            base=helper.RED,
            new=helper.WHITE,
        )

    data = helper.load_save_file(path)
    save_stats = data["save_stats"]
    save_data: bytes = data["save_data"]

    if not clear_tutorial.is_tutorial_cleared(save_stats):
        save_stats = clear_tutorial.clear_tutorial(save_stats)
        save_data = serialise_save.start_serialize(save_stats)

    while True:
        save_stats = parse_save.start_parse(save_data, save_stats["version"])
        save_data = patcher.patch_save_data(save_data, save_stats["version"])
        save_stats = feature_handler.menu(save_stats, path)
        save_data = serialise_save.start_serialize(save_stats)
        save_data = patcher.patch_save_data(save_data, save_stats["version"])

        if config_manager.get_config_value_category("SAVE_CHANGES", "SAVE_CHANGES_ON_EDIT"):
            helper.write_file_bytes(path, save_data)
            helper.colored_text(
                locale_manager.search_key("save_data_saved") % path,
                base=helper.GREEN,
                new=helper.WHITE,
            )

        temp_path = os.path.join(config_manager.get_app_data_folder(), "SAVE_DATA_temp")
        helper.write_file_bytes(temp_path, save_data)

        if config_manager.get_config_value_category("SAVE_CHANGES", "ALWAYS_EXPORT_JSON"):
            helper.export_json(save_stats, path + ".json")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        try:
            locale_manager = locale_handler.LocalManager.from_config()
            error_txt = locale_manager.search_key("generic_error") % e
        except Exception:
            error_txt = "An error has occurred: %s" % e
        helper.colored_text(error_txt, base=helper.RED, new=helper.WHITE)
        traceback.print_exc()
        helper.exit_check_changes()