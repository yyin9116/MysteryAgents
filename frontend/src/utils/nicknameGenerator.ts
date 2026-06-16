/**
 * 根据 Agent 特性生成个性昵称
 */

type MBTIType = string;
type IQLevel = "High" | "Mid" | "Low";

// MBTI 性格特征映射
const MBTI_TRAITS: Record<string, string[]> = {
    // 外向型
    "E": ["活泼", "外向", "热情", "开朗", "健谈", "社交"],
    // 内向型
    "I": ["内敛", "安静", "深思", "独立", "专注", "神秘"],
    // 直觉型
    "N": ["创意", "理想", "想象", "抽象", "未来", "灵感"],
    // 感觉型
    "S": ["务实", "实际", "细节", "现实", "经验", "传统"],
    // 思考型
    "T": ["理性", "逻辑", "客观", "分析", "冷静", "果断"],
    // 情感型
    "F": ["感性", "温暖", "共情", "和谐", "体贴", "温柔"],
    // 判断型
    "J": ["计划", "有序", "果断", "坚定", "目标", "执行"],
    // 感知型
    "P": ["灵活", "随性", "开放", "适应", "自由", "探索"],
};

// IQ 级别特征
const IQ_TRAITS: Record<IQLevel, string[]> = {
    High: ["聪明", "睿智", "天才", "机敏", "敏锐", "洞察"],
    Mid: ["普通", "正常", "一般", "标准", "常规", "平衡"],
    Low: ["简单", "纯真", "天真", "直率", "朴实", "单纯"],
};

// 性别相关后缀（根据性格推断）
const GENDER_SUFFIXES: Record<string, string[]> = {
    // 偏女性化特征
    feminine: ["小仙女", "小公主", "小可爱", "小甜心", "小精灵", "小天使"],
    // 偏男性化特征
    masculine: ["小王子", "小战士", "小勇士", "小英雄", "小骑士", "小侠客"],
    // 中性特征
    neutral: ["小萌新", "小菜鸟", "小透明", "小新人", "小玩家", "小角色"],
};

// 根据 MBTI 推断性别倾向
function inferGenderTendency(mbti: MBTIType): "feminine" | "masculine" | "neutral" {
    // F 类型（情感型）更倾向于女性化
    if (mbti.includes("F")) {
        // ENFP, INFP, ESFJ, ISFJ 等
        if (mbti.includes("P") || mbti.includes("J")) {
            return "feminine";
        }
    }
    // T 类型（思考型）更倾向于男性化
    if (mbti.includes("T")) {
        // ENTJ, INTJ, ESTJ, ISTJ 等
        if (mbti.includes("J")) {
            return "masculine";
        }
    }
    // 默认中性
    return "neutral";
}

/**
 * 生成个性昵称
 * @param mbti MBTI 类型
 * @param iqLevel IQ 级别
 * @returns 个性昵称，例如："一意孤行的小笨仙女"
 */
export function generateNickname(mbti: MBTIType, iqLevel: IQLevel): string {
    // 获取 MBTI 各维度特征
    const traits: string[] = [];
    
    // 第一个字母：E/I
    const ei = mbti[0];
    traits.push(...MBTI_TRAITS[ei] || []);
    
    // 第二个字母：S/N
    const sn = mbti[1];
    traits.push(...MBTI_TRAITS[sn] || []);
    
    // 第三个字母：T/F
    const tf = mbti[2];
    traits.push(...MBTI_TRAITS[tf] || []);
    
    // 第四个字母：J/P
    const jp = mbti[3];
    traits.push(...MBTI_TRAITS[jp] || []);
    
    // IQ 特征
    traits.push(...IQ_TRAITS[iqLevel] || []);
    
    // 随机选择性格特征（2-3个）
    const selectedTraits: string[] = [];
    const shuffled = [...traits].sort(() => Math.random() - 0.5);
    
    // 选择 2-3 个特征
    const numTraits = Math.floor(Math.random() * 2) + 2; // 2 或 3
    for (let i = 0; i < numTraits && i < shuffled.length; i++) {
        if (!selectedTraits.includes(shuffled[i])) {
            selectedTraits.push(shuffled[i]);
        }
    }
    
    // 推断性别倾向
    const genderTendency = inferGenderTendency(mbti);
    const genderSuffixes = GENDER_SUFFIXES[genderTendency];
    const suffix = genderSuffixes[Math.floor(Math.random() * genderSuffixes.length)];
    
    // 组合昵称：特征1 + 特征2 + 的 + 后缀
    // 例如："一意孤行的小笨仙女"
    const prefix = selectedTraits.slice(0, -1).join("") + selectedTraits[selectedTraits.length - 1];
    
    return `${prefix}的${suffix}`;
}

/**
 * 根据 Agent ID 生成固定昵称（相同 ID 总是返回相同昵称）
 * @param agentId Agent ID
 * @param mbti MBTI 类型
 * @param iqLevel IQ 级别
 * @returns 固定的个性昵称
 */
export function generateStableNickname(agentId: string, mbti: MBTIType, iqLevel: IQLevel): string {
    // 使用 agentId 作为随机种子，确保相同 ID 总是得到相同昵称
    let hash = 0;
    for (let i = 0; i < agentId.length; i++) {
        hash = ((hash << 5) - hash) + agentId.charCodeAt(i);
        hash = hash & hash; // Convert to 32bit integer
    }
    
    // 获取特征
    const ei = mbti[0];
    const sn = mbti[1];
    const tf = mbti[2];
    const jp = mbti[3];
    
    const allTraits = [
        ...(MBTI_TRAITS[ei] || []),
        ...(MBTI_TRAITS[sn] || []),
        ...(MBTI_TRAITS[tf] || []),
        ...(MBTI_TRAITS[jp] || []),
        ...(IQ_TRAITS[iqLevel] || []),
    ];
    
    // 使用 hash 选择特征
    const numTraits = 2 + (Math.abs(hash) % 2); // 2 或 3
    const selectedTraits: string[] = [];
    let seed = Math.abs(hash);
    
    for (let i = 0; i < numTraits && selectedTraits.length < numTraits; i++) {
        const index = seed % allTraits.length;
        const trait = allTraits[index];
        if (!selectedTraits.includes(trait)) {
            selectedTraits.push(trait);
        }
        seed = Math.floor(seed / allTraits.length) || 1;
    }
    
    // 如果特征不够，补充
    while (selectedTraits.length < 2) {
        const randomTrait = allTraits[Math.abs(hash + selectedTraits.length) % allTraits.length];
        if (!selectedTraits.includes(randomTrait)) {
            selectedTraits.push(randomTrait);
        }
    }
    
    // 推断性别倾向
    const genderTendency = inferGenderTendency(mbti);
    const genderSuffixes = GENDER_SUFFIXES[genderTendency];
    const suffixIndex = Math.abs(hash) % genderSuffixes.length;
    const suffix = genderSuffixes[suffixIndex];
    
    // 组合昵称
    const prefix = selectedTraits.join("");
    
    return `${prefix}的${suffix}`;
}








