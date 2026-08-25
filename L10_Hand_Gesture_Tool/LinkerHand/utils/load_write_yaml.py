#!/usr/bin/env python3 
# -*- coding: utf-8 -*-
'''
Author: HJX
Date: 2025-04-01 14:09:21
LastEditors: Please set LastEditors
LastEditTime: 2025-04-11 10:19:01
FilePath: /LinkerHand_Python_SDK/LinkerHand/utils/load_write_yaml.py
Description: 
symbol_custom_string_obkorol_copyright: 
'''
import yaml, os, sys
class LoadWriteYaml():
    def __init__(self):
        # 由于是API形式，这里要给配置文件目录绝对路径
        #yaml_path = "/home/linkerhand/ROS2/linker_hand_ros2_sdk/src/linker_hand_ros2_sdk/linker_hand_ros2_sdk/LinkerHand"
        yaml_path = os.path.dirname(os.path.abspath(__file__)) + "/../../LinkerHand"
        self.setting_path = yaml_path+"/config/setting.yaml"
        self.l7_positions = yaml_path+"/config/L7_positions.yaml"
        self.l10_positions = yaml_path+"/config/L10_positions.yaml"
        self.l20_positions = yaml_path+"/config/L20_positions.yaml"
        self.l21_positions = yaml_path+"/config/L21_positions.yaml"
        self.l25_positions = yaml_path+"/config/L25_positions.yaml"
        

    def load_setting_yaml(self):
        try:
            with open(self.setting_path, 'r', encoding='utf-8') as file:
                setting = yaml.safe_load(file)
                self.sdk_version = setting["VERSION"]
                self.left_hand_exists = setting['LINKER_HAND']['LEFT_HAND']['EXISTS']
                self.left_hand_names = setting['LINKER_HAND']['LEFT_HAND']['NAME']
                self.left_hand_joint = setting['LINKER_HAND']['LEFT_HAND']['JOINT']
                self.left_hand_force = setting['LINKER_HAND']['LEFT_HAND']['TOUCH']
                self.right_hand_exists = setting['LINKER_HAND']['RIGHT_HAND']['EXISTS']
                self.right_hand_names = setting['LINKER_HAND']['RIGHT_HAND']['NAME']
                self.right_hand_joint = setting['LINKER_HAND']['RIGHT_HAND']['JOINT']
                self.right_hand_force = setting['LINKER_HAND']['RIGHT_HAND']['TOUCH']
                self.password = setting['PASSWORD']
        except Exception as e:
            setting = None
            print(f"Error reading setting.yaml: {e}")
        self.setting = setting
        return self.setting
    
    def load_action_yaml(self,hand_joint="",hand_type=""):
        if hand_joint == "L20":
            action_path = self.l20_positions
        elif hand_joint == "L10":
            action_path = self.l10_positions
        elif hand_joint == "L25":
            action_path = self.l25_positions
        elif hand_joint == "L21":
            action_path = self.l21_positions
        elif hand_joint == "L7":
            action_path = self.l7_positions
            print(action_path)
        try:
            with open(action_path, 'r', encoding='utf-8') as file:
                yaml_data = yaml.safe_load(file)
                if hand_type == "left":
                    self.action_yaml = yaml_data["LEFT_HAND"]
                else:
                    self.action_yaml = yaml_data["RIGHT_HAND"]
        except Exception as e:
            self.action_yaml = None
            print(f"yaml配置文件不存在: {e}")
        return self.action_yaml 

    def write_to_yaml(self, action_name, action_pos,hand_joint="",hand_type=""):
        a = False
        if hand_joint == "L20":
            action_path = self.l20_positions
        elif hand_joint == "L10":
            action_path = self.l10_positions
        elif hand_joint == "L7":
            action_path = self.l7_positions
        elif hand_joint == "L21":
            action_path = self.l21_positions
        elif hand_joint == "L25":
            action_path = self.l25_positions
        try:
            with open(action_path, 'r', encoding='utf-8') as file:
                yaml_data = yaml.safe_load(file)
                print(yaml_data)
            if hand_type == "left":
                if yaml_data["LEFT_HAND"] == None:
                    yaml_data["LEFT_HAND"] = []
                yaml_data["LEFT_HAND"].append({"ACTION_NAME": action_name, "POSITION": action_pos})
            elif hand_type == "right":
                if yaml_data["RIGHT_HAND"] == None:
                    yaml_data["RIGHT_HAND"] = []
                yaml_data["RIGHT_HAND"].append({"ACTION_NAME": action_name, "POSITION": action_pos})
            with open(action_path, 'w', encoding='utf-8') as file:
                yaml.safe_dump(yaml_data, file, allow_unicode=True)
            a = True
        except Exception as e:
            a = False
            print(f"Error writing to yaml file: {e}")
        return a

    # ==============================================================================
    # 以下是添加并修正了缩进的 delete_from_yaml 方法
    # ==============================================================================
    def delete_from_yaml(self, action_name, hand_joint="", hand_type=""):
        """
        从正确的YAML配置文件中，根据动作名称删除一个动作。
        """
        # 步骤 1: 使用与 write_to_yaml 完全相同的逻辑来选择正确的文件路径
        action_path = ""
        if hand_joint == "L20":
            action_path = self.l20_positions
        elif hand_joint == "L10":
            action_path = self.l10_positions
        elif hand_joint == "L7":
            action_path = self.l7_positions
        elif hand_joint == "L21":
            action_path = self.l21_positions
        elif hand_joint == "L25":
            action_path = self.l25_positions
        else:
            print(f"错误: 未知的关节类型 '{hand_joint}'，无法删除动作。")
            return False

        try:
            # 步骤 2: 读取整个YAML文件的数据
            with open(action_path, 'r', encoding='utf-8') as file:
                yaml_data = yaml.safe_load(file)

            # 如果文件为空或不是一个字典，则无法继续
            if not isinstance(yaml_data, dict):
                print(f"警告: 动作文件 {action_path} 为空或格式不正确。")
                return False

            # 步骤 3: 根据手类型（左/右）找到对应的动作列表，并执行删除操作
            if hand_type == "left":
                key = "LEFT_HAND"
            elif hand_type == "right":
                key = "RIGHT_HAND"
            else:
                print(f"错误: 未知的手类型 '{hand_type}'。")
                return False

            # 检查对应的手部动作列表是否存在且不为空
            if key not in yaml_data or not yaml_data[key]:
                print(f"在 {action_path} 中未找到 '{key}' 的动作列表，或列表为空。")
                return False

            # 筛选出需要保留的动作（即排除掉要删除的动作）
            original_count = len(yaml_data[key])
            actions_to_keep = [action for action in yaml_data[key] if action.get("ACTION_NAME") != action_name]

            # 如果筛选前后数量不变，说明没有找到要删除的动作
            if len(actions_to_keep) == original_count:
                print(f"未在 '{key}' 列表中找到名为 '{action_name}' 的动作。")
                return False

            # 步骤 4: 用筛选后的新列表替换旧列表
            yaml_data[key] = actions_to_keep

            # 步骤 5: 将更新后的整个数据结构写回文件
            with open(action_path, 'w', encoding='utf-8') as file:
                yaml.safe_dump(yaml_data, file, allow_unicode=True, sort_keys=False)
            
            print(f"成功删除动作: '{action_name}'")
            return True

        except FileNotFoundError:
            print(f"错误: 动作文件 {action_path} 未找到。")
            return False
        except Exception as e:
            print(f"处理YAML文件时发生错误: {e}")
            return False
