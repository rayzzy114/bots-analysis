class MessageManager:
    def __init__(self):
        self.messages = {}
        self.photo_messages = {}

    async def set_message(self, user_id, message_id):
        self.messages[user_id] = message_id

    async def set_photo_message(self, user_id, message_id):
        self.photo_messages[user_id] = message_id

    async def delete_message(self, user_id):
        if user_id in self.messages:
            message = self.messages[user_id]
            await message.delete()
            del self.messages[user_id]

    async def delete_photo_message(self, user_id):
        if user_id in self.photo_messages:
            message = self.photo_messages[user_id]
            await message.delete()
            del self.photo_messages[user_id]

    async def delete_main_menu(self, user_id):
        if user_id in self.photo_messages:
            message = self.photo_messages[user_id]
            await message.delete()
            del self.photo_messages[user_id]
            if user_id in self.messages and self.messages[user_id] == message:
                del self.messages[user_id]
        elif user_id in self.messages:
            message = self.messages[user_id]
            await message.delete()
            del self.messages[user_id]


manager = MessageManager()

