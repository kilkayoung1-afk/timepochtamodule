const { SlashCommandBuilder } = require('discord.js');
const EmojiPackGenerator = require('../path/to/emojiPackGenerator');

// Укажи путь к твоему шаблону (картинка должна быть квадратной)
const generator = new EmojiPackGenerator(path.join(__dirname, '../assets/template.png'));

module.exports = {
    data: new SlashCommandBuilder()
        .setName('create-pack')
        .setDescription('Создает пакк из 49 эмодзи с вашей надписью')
        .addStringOption(option =>
            option.setName('text')
                .setDescription('Надпись, которая будет на эмодзи')
                .setRequired(true)
                .setMaxLength(10) // Ограничиваем длину, чтобы текст влез на картинку
        ),
        
    async execute(interaction) {
        const text = interaction.options.getString('text');
        
        // Проверка на наличие слотов для эмодзи (Опционально)
        const availableSlots = interaction.guild.maximumEmojis - interaction.guild.emojis.cache.size;
        if (availableSlots < 49) {
            return interaction.reply({ 
                content: `На сервере недостаточно места для эмодзи. Нужно: 49, свободно: ${availableSlots}`, 
                ephemeral: true 
            });
        }

        await interaction.deferReply({ content: `Генерирую пакк из 49 эмодзи с надписью **${text}**... Это займет немного времени.` });

        try {
            // Генерируем пакк в памяти
            const emojiPack = await generator.generatePack(text);

            let uploadedCount = 0;

            // Загружаем эмодзи на сервер с задержкой, чтобы избежать рейт-лимита Discord
            for (const emoji of emojiPack) {
                try {
                    await interaction.guild.emojis.create({
                        attachment: emoji.buffer,
                        name: emoji.name,
                    });
                    uploadedCount++;
                    // Задержка 500мс между созданием эмодзи (важно для Discord API)
                    await new Promise(resolve => setTimeout(resolve, 500)); 
                } catch (err) {
                    console.error(`Ошибка при загрузке эмодзи ${emoji.name}:`, err);
                }
            }

            await interaction.editReply(`✅ Успешно создано ${uploadedCount}/49 эмодзи с надписью **${text}**!`);

        } catch (error) {
            console.error(error);
            await interaction.editReply('❌ Произошла ошибка при генерации или загрузке эмодзи.');
        }
    },
};
