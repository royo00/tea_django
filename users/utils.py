def replace_avatar(user, new_file):
    """更新头像并清理旧文件，避免 media 目录堆积孤儿文件。"""
    old_name = user.avatar.name if user.avatar else None
    user.avatar = new_file
    user.save(update_fields=["avatar"])
    if old_name and old_name != user.avatar.name:
        user.avatar.storage.delete(old_name)
