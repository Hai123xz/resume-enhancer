try:
    from config.config_file import WRITE_MODEL_NAME
except ImportError:
    # Deployment guard: text-only agent calls should use the Groq text model.
    WRITE_MODEL_NAME = "llama3-70b-8192"

def score_resume(client ,resume_text: str, job_text: str):
    grader_prompt = f"""
        You are an expert technical recruiter. 
        Evaluate how well this resume matches the job description.
        
        Job Description: {job_text}
        Resume: {resume_text}
        
        Return ONLY a valid JSON object with two keys:
        - "score": an integer from 0 to 10.
        - "feedback": a brief string explaining the score.
    """

    response = client.chat.completions.create(
        model = WRITE_MODEL_NAME,
        messages = [{"role":"user", "content": grader_prompt}],
        response_format = {"type": "json_object"}
    )

    return response.choices[0].message.content

def rewrite_section(client, resume_text, job_text, grader_feedback):
    prompt = f"""
    You are an expert technical resume writer. Your task is to rewrite the resume to maximize its alignment with the target job description.
    
    Target Job Description:
    {job_text}
    
    Current Resume:
    {resume_text}
    
    Grader Feedback:
    {grader_feedback}
    
    Instructions:
    1. Prioritize fixing the specific issues mentioned in the Grader Feedback.
    2. Naturally integrate missing keywords from the Job Description.
    3. Rewrite bullet points to start with strong action verbs and emphasize measurable impact.
    4. CRITICAL: DO NOT invent new skills, jobs, education, or experiences. Only optimize and rephrase existing facts.
    5. Output ONLY the rewritten resume text in clean Markdown format.
    """

    response = client.chat.completions.create(
        model = WRITE_MODEL_NAME,
        messages = [{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
