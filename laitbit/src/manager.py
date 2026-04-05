class MessageManager:
    def __init__(self):
        self.messages = {}

    async def set_message(self, user_id, message_id):
        self.messages[user_id] = message_id

    async def delete_message(self, user_id):
        if user_id in self.messages:
            message = self.messages[user_id]
            await message.delete()
            del self.messages[user_id]


manager = MessageManager()
