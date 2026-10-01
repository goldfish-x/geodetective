// 双端共享的唯一事实源：计分公式、模式参数、关卡结构。
// 浏览器与服务端都从这里取，避免 P1 服务端判分后出现双端漂移。
export * from './scoring.js'
export * from './quiz.js'
