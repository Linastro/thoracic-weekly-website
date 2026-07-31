"""5 个病种检索式定义(MeSH + tiab 组合)。"""
DISEASES=[
{"slug":"lung_cancer","name_zh":"肺癌","query":'"Lung Neoplasms"[Mesh] OR lung cancer[tiab] OR NSCLC[tiab] OR SCLC[tiab] OR lung adenocarcinoma[tiab] OR lung squamous cell carcinoma[tiab]'},
{"slug":"esophageal","name_zh":"食管癌","query":'"Esophageal Neoplasms"[Mesh] OR esophageal cancer[tiab] OR ESCC[tiab] OR esophageal adenocarcinoma[tiab] OR esophageal squamous cell carcinoma[tiab]'},
{"slug":"mediastinal","name_zh":"纵隔肿瘤","query":'"Mediastinal Neoplasms"[Mesh] OR mediastinal tumor[tiab] OR thymoma[tiab] OR thymic carcinoma[tiab] OR thymic epithelial tumor[tiab] OR mediastinal germ cell tumor[tiab]'},
{"slug":"tracheal","name_zh":"气管疾病","query":'"Tracheal Neoplasms"[Mesh] OR "Tracheal Stenosis"[Mesh] OR tracheal cancer[tiab] OR tracheal tumor[tiab] OR tracheal stenosis[tiab] OR tracheal resection[tiab] OR airway surgery[tiab] OR tracheoplasty[tiab]'},
{"slug":"chest_wall_injury","name_zh":"气胸·胸外伤·肋骨骨折·胸壁畸形","query":'"Pneumothorax"[Mesh] OR "Thoracic Injuries"[Mesh] OR "Rib Fractures"[Mesh] OR "Pulmonary Contusion"[Mesh] OR "Funnel Chest"[Mesh] OR spontaneous pneumothorax[tiab] OR flail chest[tiab] OR SSRF[tiab] OR Nuss procedure[tiab] OR pectus excavatum[tiab] OR chest wall reconstruction[tiab]'},]
MEDIASTINAL_SUPPLEMENT_QUERY='"Mediastinum"[Mesh] OR thymic[tiab] OR anterior mediastinal[tiab]'
DISEASE_BY_SLUG={d['slug']:d for d in DISEASES}
