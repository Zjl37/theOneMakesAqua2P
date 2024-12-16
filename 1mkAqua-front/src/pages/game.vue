<script setup lang="ts">
import { defineComponent, ref, reactive, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { io, Socket } from "socket.io-client";
import { ElMessage, ElMessageBox } from "element-plus";
import { nextTick } from "vue";

interface Room {
  id: string;
  title: string;
  players: number;
}

interface GameState {
  roomId: string;
  isPlayerTurn: boolean;
  messages: string[];
  opponentTyping: string;
  judgeMessage: string;
  gameStarted: boolean;
  gameOver: boolean;
  combo: number;
  wordHistory: string[];
  emojiHistory: string[];
  gameOverReason: string;
  countDown: number;
  waitingReply: boolean;
  gameOverNormal: boolean;
  opponentName: string;
}

const socket: Socket = io(window.location.host.split(":")[0] + ":3000");

const router = useRouter();

// Reactive State
const rooms = ref<Room[]>([]);
const roomTitle = ref("");
const roomLlmKey = ref("");
const currentRoom = ref<string | null>(null);
const INIT_GMAE_STATE = {
  roomId: "",
  isPlayerTurn: false,
  messages: [],
  opponentTyping: "",
  judgeMessage: "",
  gameStarted: false,
  gameOver: false,
  combo: 0,
  wordHistory: ["水"],
  emojiHistory: ["💧"],
  gameOverReason: "",
  countDown: 0,
  waitingReply: false,
  gameOverNormal: true,
  opponentName: "",
};
const gameState = reactive<GameState>(structuredClone(INIT_GMAE_STATE));
const playerText = ref("");
const TIME_LIMIT = 19;
const nickname = ref("");

// Computed
const isInRoom = computed(() => currentRoom.value !== null);
const inviteLink = computed(
  () => window.location.origin + `/game?invite=` + gameState.roomId,
);
let countTimeout = 0;

function doCountDown() {
  gameState.countDown -= 1;
  if (gameState.countDown > 0) {
    countTimeout = setTimeout(doCountDown, 1000);
  }
}

function resetCountdown(limit = TIME_LIMIT) {
  clearTimeout(countTimeout);
  gameState.countDown = limit;
  countTimeout = setTimeout(doCountDown, 1000);
}

// Socket Event Handlers
function setupSocketListeners() {
  // Receive available rooms
  socket.on("updateRooms", (updatedRooms: Room[]) => {
    rooms.value = updatedRooms;
  });

  // Join room success or failure
  socket.on("joinRoomSuccess", (roomId: string) => {
    currentRoom.value = roomId;
    gameState.roomId = roomId;
    ElMessage.success("成功加入房间！");
  });

  socket.on("joinRoomFail", (message: string) => {
    ElMessage.error(message);
  });

  socket.on(
    "gameStart",
    (data: { init_word: string; my_turn: boolean; opponent_name: string }) => {
      gameState.isPlayerTurn = data.my_turn;
      gameState.wordHistory = [data.init_word];
      gameState.gameStarted = true;
      gameState.opponentName = data.opponent_name;
      console.log(data.opponent_name);
      resetCountdown();
    },
  );

  socket.on("setPending", () => {
    console.log("set pending...");
    clearTimeout(countTimeout);
    gameState.waitingReply = true;
  });

  // Receive judgment on submitted text
  socket.on(
    "textJudgment",
    (data: {
      correct: boolean;
      message: string;
      word: string;
      emoji: string;
      my_turn: boolean;
    }) => {
      gameState.waitingReply = false;
      gameState.judgeMessage = data.message;
      gameState.isPlayerTurn = data.my_turn;
      gameState.wordHistory.push(data.word);
      gameState.emojiHistory.push(data.emoji);
      if (!data.correct) {
        gameState.gameOver = true;
        if (data.my_turn) {
          gameState.gameOverReason = `你获胜了！（对方失误）`;
          ElMessageBox.alert(
            gameState.gameOverReason + "\n\n" + gameState.judgeMessage,
            "游戏结束",
            {
              type: "success",
            },
          );
        } else {
          gameState.gameOverReason = `你失败了！`;
          ElMessageBox.alert(
            gameState.gameOverReason + "\n\n" + gameState.judgeMessage,
            "游戏结束",
            {
              type: "error",
            },
          );
        }
      } else {
        gameState.combo += 1;
        resetCountdown();
      }
    },
  );

  // Receive opponent typing updates
  socket.on("opponentTyping", (text: string) => {
    gameState.opponentTyping = text;
  });

  // Opponent leaves or disconnects
  socket.on("gameOver", (data: { win: boolean; reason: string }) => {
    gameState.gameOver = true;
    gameState.gameOverReason = data.reason;
    gameState.gameOverNormal = false;
    ElMessageBox.alert("对方退出了游戏。你获胜！", "游戏结束", {
      type: "success",
    });
  });

  // General updates
  socket.on("serverMessage", (message: string) => {
    ElMessage.info(message);
  });

  socket.on("serverError", (data: { what: string; retry: boolean }) => {
    ElMessage.error(data.what);
    gameState.waitingReply = !data.retry;
  });
}

// Methods
function createRoom() {
  if (!roomTitle.value.trim()) {
    ElMessage.warning("房间名不得为空！");
    return;
  }
  if (!roomLlmKey.value.startsWith("sk-") || roomLlmKey.value.length != 35) {
    ElMessage.warning("请输入有效的 Dashscope API Key！");
    return;
  }

  socket.emit("createRoom", {
    title: roomTitle.value.trim(),
    llmKey: roomLlmKey.value,
    my_nickname: nickname.value,
  });
  roomTitle.value = "";
}

function joinRoom(roomId: string) {
  socket.emit("joinRoom", { room_id: roomId, my_nickname: nickname.value });
}

function submitText() {
  const text = playerText.value.trim();
  if (!text) {
    ElMessage.warning("文本不得为空！");
    return;
  }
  if (gameState.wordHistory.indexOf(text) !== -1) {
    ElMessage.warning("不得提交已出现过的词语！");
    return;
  }
  clearTimeout(countTimeout);
  gameState.waitingReply = true;
  socket.emit("submitText", {
    roomId: gameState.roomId,
    text,
  });
  playerText.value = "";
}

function leaveRoom() {
  if (isInRoom.value) {
    socket.emit("leaveRoom", gameState.roomId);
    currentRoom.value = null;
    Object.assign(gameState, INIT_GMAE_STATE);
  }
}

function updateTyping() {
  socket.emit("typing", { roomId: gameState.roomId, text: playerText.value });
}

// Lifecycle Hooks
onMounted(async () => {
  try {
    await nextTick();
    const { value } = await ElMessageBox.prompt("输入你的昵称", "欢迎", {
      confirmButtonText: "OK",
      cancelButtonText: "Cancel",
      "show-close": false,
      showCancelButton: false,
      inputPattern: /.+/,
      inputErrorMessage: "昵称不得为空！",
      closeOnClickModal: false,
      closeOnPressEscape: false,
    });

    nickname.value = value;
  } catch (e) {
    console.log("reload");
    console.log(e);
    location.reload();
  }

  setupSocketListeners();
  socket.emit("getRooms");
  const invite = router.currentRoute.value.query?.invite;
  if (typeof invite == "string") {
    joinRoom(invite);
  }
});
</script>

<template>
  <div class="game-container">
    <!-- Room Selection -->
    <div v-if="!isInRoom" class="room-selection">
      <h1>太一生水 2P</h1>
      <!-- <h2>Available Rooms</h2> -->
      <el-input v-model="roomTitle" placeholder="房间名称" class="room-input" />
      <el-input
        v-model="roomLlmKey"
        placeholder="Dashscope API Key"
        class="room-input"
      />
      <p style="font-size: 9pt; color: darkgray">
        您的 API Key 将仅用于此局游戏中调用 qwen-plus
        大模型来判断答案对错。我们承诺不会在此局游戏结束后持久地储存您的 API
        Key.
      </p>
      <el-button type="primary" @click="createRoom">创建房间</el-button>

      <el-table :data="rooms" style="margin-top: 20px">
        <el-table-column prop="title" label="Room Title" />
        <el-table-column prop="players" label="Players" />
        <el-table-column label="Actions">
          <template #default="{ row }">
            <el-button size="small" @click="joinRoom(row.id)">Join</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="color: gray; margin-top: 12em">
        <p style="text-align: start">
          太一生水，水反辅太一，是以成天。天反辅太一，是以成地。天地相辅也，是以成神明；神明复相辅也，是以成侌昜；侌昜复相辅也，是以成四时；四时复辅也，是以成仓然；仓然复相辅也，是以成湿燥；湿燥复相辅也，成岁而止。
        </p>
        <p style="text-align: end">——郭店楚简</p>
      </div>
    </div>

    <!-- Game Room -->
    <div v-else class="game-room">
      <h2>房间：{{ gameState.roomId }}</h2>
      <el-button type="danger" @click="leaveRoom">离开房间</el-button>

      <div v-if="gameState.gameStarted" class="game-board">
        <el-row>
          <el-col :span="8">{{ nickname }}</el-col>
          <el-col :span="8">VS</el-col>
          <el-col :span="8">{{ gameState.opponentName }}</el-col>
        </el-row>
        <!-- <h3>Opponent is typing:</h3> -->
        <!-- <p>{{ gameState.opponentTyping }}</p> -->

        <p style="color: gray">道生一，一生二，二生三，三生万物</p>
        <p style="font-size: 2em" v-if="gameState.gameOver">
          {{ gameState.gameOverReason }}
        </p>
        <p style="font-size: 2em" v-else>
          那么，<span style="color: darkcyan">{{
            gameState.wordHistory.at(-1)
          }}</span
          >能生成什么？
        </p>

        <p>连击数：{{ gameState.combo }}</p>
        <template v-if="!gameState.gameOver">
          <h3 v-if="gameState.isPlayerTurn">轮到你了</h3>
          <h3 v-else>轮到对方</h3>
        </template>
        <el-row>
          <el-col :span="20">
            <el-input
              v-model="playerText"
              :placeholder="
                gameState.isPlayerTurn
                  ? `输入一个自然事物`
                  : gameState.opponentTyping
              "
              :disabled="
                !gameState.isPlayerTurn ||
                gameState.gameOver ||
                gameState.waitingReply
              "
              @input="updateTyping"
              @keyup.enter="submitText"
              maxlength="15"
            />
          </el-col>
          <el-col :span="4">
            <el-button
              type="primary"
              @click="submitText"
              :disabled="
                !gameState.isPlayerTurn ||
                gameState.gameOver ||
                gameState.waitingReply
              "
              >提交</el-button
            >
          </el-col>
        </el-row>
        <el-progress
          v-show="!gameState.gameOver"
          :percentage="(gameState.countDown / TIME_LIMIT) * 100"
          :stroke-width="20"
          :color="gameState.isPlayerTurn ? `orange` : `gray`"
          text-inside
          :indeterminate="gameState.waitingReply"
          :format="() => `${gameState.countDown}`"
        />

        <p style="font-size: 1.25em">{{ gameState.judgeMessage }}</p>
        <template
          v-if="gameState.emojiHistory.length > 1 && gameState.gameOverNormal"
        >
          <p style="font-weight: bold">
            <span>{{ gameState.wordHistory.at(-2) }}</span>
            <span v-if="gameState.gameOver" style="color: red">不能</span>
            <span v-else style="color: darkgreen">可以</span>
            <span>生成</span>
            <span>{{ gameState.wordHistory.at(-1) }}</span>
            <span>！</span>
          </p>
          <p>
            <span style="font-size: 5em">{{
              gameState.emojiHistory.at(-2)
            }}</span>
            <span>　</span>
            <span v-if="gameState.gameOver" style="font-size: 1.75em">😵</span>
            <span v-else style="font-size: 1.75em">➡️</span>
            <span>　</span>
            <span style="font-size: 5em">{{
              gameState.emojiHistory.at(-1)
            }}</span>
          </p>
        </template>

        <p style="text-align: start">
          成就：
          <span
            >{{ gameState.emojiHistory[0] }}
            {{ gameState.wordHistory[0] }}</span
          >
          <span
            v-for="[em, word] in gameState.emojiHistory
              .slice(1, -1)
              .map((e, i) => [e, gameState.wordHistory[i + 1]])"
          >
            <span> → </span>
            <span>{{ em }} {{ word }}</span>
          </span>
          <template
            v-if="
              !gameState.gameOverNormal && gameState.emojiHistory.length > 1
            "
          >
            <span> → </span>
            <span
              >{{ gameState.emojiHistory.at(-1) }}
              {{ gameState.wordHistory.at(-1) }}</span
            >
          </template>
        </p>
      </div>
      <div v-else>
        <h3>等待其他玩家加入……</h3>
        <el-progress :percentage="50" :duration="5" :indeterminate="true" />

        <h3>邀请链接：</h3>
        <p>{{ inviteLink }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-container {
  padding: 20px;
}

.room-selection {
  max-width: 600px;
  margin: 0 auto;
}

.room-input {
  margin-bottom: 10px;
}

.game-room {
  max-width: 800px;
  margin: 0 auto;
}

.game-board {
  margin-top: 20px;
}

.room-selection {
  min-height: 80vh;
  background-image: url("/bamboo-slips.webp");
  background-repeat: no-repeat;
  background-size: 75%;
  background-position: bottom;
}

.game-container {
  min-height: 100%;
}
</style>

<style>
body .ep-overlay {
  position: fixed;
}
</style>
